"""The validated tool surface available to the interview workflow.

The workflow never issues its own SQL. Every read and write goes through one of
these functions, which:

  1. validate their arguments,
  2. enforce that the acting user owns the row being touched, and
  3. append a row to `tool_logs` describing the call.

`tool_logs` is written on its own short-lived session so the audit trail survives
even when the caller's transaction is rolled back. SQLite is the exception - see
AUDIT_ON_SHARED_SESSION below.
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import tokenize
from app.ai.llm import InterviewContext, get_llm_provider
from app.ai.prompts import build_candidate_block, build_job_block
from app.ai.retrieval import RetrievedChunk, search_chunks
from app.ai.schemas import (
    AnswerEvaluation,
    GeneratedQuestion,
    GeneratedQuestionSet,
    ImprovementPlanOutput,
)
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import DocumentType, JobDescription
from app.models.enums import Difficulty, QuestionCategory
from app.models.interview import (
    Answer,
    Evaluation,
    ImprovementPlan,
    Interview,
    InterviewQuestion,
    ToolLog,
)
from app.models.user import CandidateProfile, User

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# SQLite serialises writers at the file level, so a second connection would block
# on the request's own open write transaction until it times out. There, the
# audit row goes through the request session instead: it is then lost on a
# rollback, which is the right trade for the environment SQLite is used in
# (tests and zero-infrastructure local runs). PostgreSQL keeps the independent
# session, where a rollback is exactly when the audit trail matters most.
AUDIT_ON_SHARED_SESSION = settings.database_url.startswith("sqlite")


class ToolError(RuntimeError):
    """Raised when a tool is called with invalid or unauthorised arguments."""


def _summarise(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, (list, tuple)):
        return f"{type(value).__name__}[{len(value)}]"
    if isinstance(value, dict):
        return f"dict({', '.join(list(value)[:5])})"
    text = str(value)
    return text[:300]


def _safe_args(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Truncate long argument values so tool_logs stays readable."""
    out: dict[str, Any] = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            out[key] = value[:500]
        elif isinstance(value, (int, float, bool, type(None))):
            out[key] = value
        elif isinstance(value, list):
            out[key] = [str(v)[:120] for v in value[:10]]
        else:
            out[key] = _summarise(value)
    return out


def tool(name: str) -> Callable[[F], F]:
    """Wrap a ToolRunner method so the call is timed, logged, and audited."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self: "ToolRunner", *args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            error: str | None = None
            summary = ""
            try:
                result = func(self, *args, **kwargs)
                summary = _summarise(result)
                return result
            except Exception as exc:
                error = f"{exc.__class__.__name__}: {exc}"
                raise
            finally:
                self._write_log(
                    tool_name=name,
                    arguments=_safe_args(kwargs),
                    result_summary=summary,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    ok=error is None,
                    error=error,
                )

        return wrapper  # type: ignore[return-value]

    return decorator


class ToolRunner:
    """Per-request tool surface, bound to one acting user."""

    def __init__(
        self, db: Session, user_id: str, interview_id: str | None = None
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.interview_id = interview_id
        self.llm = get_llm_provider()

    # -- audit -------------------------------------------------------------- #

    def _write_log(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        result_summary: str,
        duration_ms: int,
        ok: bool,
        error: str | None,
    ) -> None:
        fields = {
            "user_id": self.user_id,
            "interview_id": self.interview_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "result_summary": result_summary,
            "duration_ms": duration_ms,
            "ok": ok,
            "error": error,
        }
        try:
            if AUDIT_ON_SHARED_SESSION:
                self.db.add(ToolLog(**fields))
                self.db.flush()
            else:
                with SessionLocal() as log_db:
                    log_db.add(ToolLog(**fields))
                    log_db.commit()
        except Exception:  # auditing must never break the request
            logger.exception("Failed to write tool_log for %s", tool_name)

    # -- ownership ---------------------------------------------------------- #

    def _owned_interview(self, interview_id: str) -> Interview:
        interview = self.db.get(Interview, interview_id)
        if interview is None or interview.user_id != self.user_id:
            raise ToolError("Interview not found")
        return interview

    # -- reads -------------------------------------------------------------- #

    @tool("get_candidate_profile")
    def get_candidate_profile(self) -> dict[str, Any]:
        user = self.db.get(User, self.user_id)
        if user is None:
            raise ToolError("User not found")
        profile = self.db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == self.user_id)
        ).scalar_one_or_none()

        if profile is None:
            return {
                "full_name": user.full_name,
                "headline": None,
                "years_of_experience": None,
                "skills": [],
                "education": [],
                "experience": [],
                "projects": [],
                "certifications": [],
                "preferred_role": None,
                "target_company": None,
                "summary": None,
            }

        return {
            "full_name": user.full_name,
            "headline": profile.headline,
            "years_of_experience": profile.years_of_experience,
            "skills": list(profile.skills or []),
            "education": list(profile.education or []),
            "experience": list(profile.experience or []),
            "projects": list(profile.projects or []),
            "certifications": list(profile.certifications or []),
            "preferred_role": profile.preferred_role,
            "target_company": profile.target_company,
            "summary": profile.summary,
        }

    @tool("retrieve_job_requirements")
    def retrieve_job_requirements(self, job_id: str | None = None) -> dict[str, Any]:
        job: JobDescription | None = None
        if job_id:
            job = self.db.get(JobDescription, job_id)
            if job is None or job.user_id != self.user_id:
                raise ToolError("Job description not found")
        else:
            job = self.db.execute(
                select(JobDescription)
                .where(
                    JobDescription.user_id == self.user_id,
                    JobDescription.is_active.is_(True),
                )
                .order_by(JobDescription.updated_at.desc())
            ).scalars().first()

        if job is None:
            return {
                "job_id": None,
                "title": "Software Engineer",
                "company": None,
                "seniority": None,
                "requirements": [],
            }

        # Pull the requirement-bearing chunks rather than the whole posting.
        chunks = search_chunks(
            self.db,
            user_id=self.user_id,
            query=(
                f"{job.title} required skills, qualifications, responsibilities, "
                "experience"
            ),
            doc_type=DocumentType.JOB_DESCRIPTION.value,
            limit=6,
        )
        requirements = [chunk.content for chunk in chunks]
        if not requirements:
            # No embedded chunks (e.g. a short pasted description): use the text.
            requirements = [
                line.strip(" -•*")
                for line in job.raw_text.splitlines()
                if len(line.strip()) > 12
            ][:12]

        return {
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "seniority": job.seniority,
            "requirements": requirements,
        }

    @tool("search_candidate_documents")
    def search_candidate_documents(
        self, query: str, doc_type: str | None = None, limit: int = 6
    ) -> list[RetrievedChunk]:
        if not query or not query.strip():
            raise ToolError("query must not be empty")
        if not 1 <= limit <= 25:
            raise ToolError("limit must be between 1 and 25")
        if doc_type is not None and doc_type not in {t.value for t in DocumentType}:
            raise ToolError(f"Unknown doc_type: {doc_type}")
        return search_chunks(
            self.db,
            user_id=self.user_id,
            query=query,
            doc_type=doc_type,
            limit=limit,
        )

    # -- context ------------------------------------------------------------ #

    def build_context(self, job_id: str | None = None) -> InterviewContext:
        """Assemble the grounded context block pair used by every prompt."""
        profile = self.get_candidate_profile()
        job = self.retrieve_job_requirements(job_id=job_id)

        role_query = " ".join(
            filter(
                None,
                [
                    job["title"],
                    profile.get("preferred_role"),
                    " ".join(profile.get("skills", [])[:12]),
                ],
            )
        )
        resume_chunks = self.search_candidate_documents(
            query=role_query or "experience skills projects",
            doc_type=DocumentType.RESUME.value,
            limit=6,
        )

        def as_lines(values: list[Any]) -> list[str]:
            lines: list[str] = []
            for value in values:
                if isinstance(value, dict):
                    lines.append(
                        " - ".join(str(v) for v in value.values() if v)[:200]
                    )
                else:
                    lines.append(str(value)[:200])
            return lines

        candidate_block = build_candidate_block(
            full_name=profile["full_name"],
            headline=profile.get("headline"),
            years_of_experience=profile.get("years_of_experience"),
            skills=[str(s) for s in profile.get("skills", [])],
            projects=as_lines(profile.get("projects", [])),
            experience=as_lines(profile.get("experience", [])),
            education=as_lines(profile.get("education", [])),
            certifications=as_lines(profile.get("certifications", [])),
            preferred_role=profile.get("preferred_role"),
            target_company=profile.get("target_company"),
            resume_excerpts=[chunk.content[:400] for chunk in resume_chunks],
        )
        job_block = build_job_block(
            title=job["title"],
            company=job.get("company"),
            seniority=job.get("seniority"),
            requirement_excerpts=[str(r)[:400] for r in job["requirements"]],
        )

        return InterviewContext(
            full_name=profile["full_name"],
            candidate_block=candidate_block,
            job_block=job_block,
            job_title=job["title"],
            skills=[str(s) for s in profile.get("skills", [])],
            projects=as_lines(profile.get("projects", [])),
            requirements=[str(r) for r in job["requirements"]],
        )

    # -- generation --------------------------------------------------------- #

    @tool("generate_interview_question")
    def generate_interview_question_set(
        self,
        ctx: InterviewContext,
        count: int,
        difficulty: Difficulty,
        seed: str,
    ) -> GeneratedQuestionSet:
        if not 1 <= count <= 20:
            raise ToolError("count must be between 1 and 20")
        return self.llm.generate_questions(ctx, count, difficulty, seed)

    @tool("generate_follow_up_question")
    def generate_follow_up(
        self,
        ctx: InterviewContext,
        previous_question: str,
        previous_answer: str,
        evaluation: AnswerEvaluation,
        target_difficulty: Difficulty,
        covered_topics: list[str],
        previous_topic: str,
        previous_category: QuestionCategory,
        seed: str,
    ) -> GeneratedQuestion:
        return self.llm.generate_follow_up(
            ctx,
            previous_question,
            previous_answer,
            evaluation,
            target_difficulty,
            covered_topics,
            previous_topic,
            previous_category,
            seed,
        )

    @tool("evaluate_answer")
    def evaluate_answer(
        self,
        question_text: str,
        category: str,
        difficulty: str,
        expected_points: list[str],
        answer_text: str,
        job_title: str,
    ) -> AnswerEvaluation:
        if not answer_text or not answer_text.strip():
            raise ToolError("answer_text must not be empty")
        return self.llm.evaluate_answer(
            question_text,
            category,
            difficulty,
            expected_points,
            answer_text,
            job_title,
        )

    @tool("create_improvement_plan")
    def create_improvement_plan(
        self,
        ctx: InterviewContext,
        transcript: str,
        overall_score: float,
        topic_scores: list[tuple[str, float]],
    ) -> ImprovementPlanOutput:
        if not 0 <= overall_score <= 10:
            raise ToolError("overall_score must be between 0 and 10")
        return self.llm.create_improvement_plan(
            ctx, transcript, overall_score, topic_scores
        )

    # -- writes ------------------------------------------------------------- #

    @tool("save_interview_question")
    def save_question(
        self,
        interview_id: str,
        question: GeneratedQuestion,
        position: int,
        source_chunk_ids: list[str] | None = None,
        follow_up_to_id: str | None = None,
    ) -> InterviewQuestion:
        self._owned_interview(interview_id)
        row = InterviewQuestion(
            interview_id=interview_id,
            position=position,
            category=question.category.value,
            difficulty=question.difficulty.value,
            topic=question.topic,
            question_text=question.question_text,
            expected_points=question.expected_points,
            source_chunk_ids=source_chunk_ids or [],
            follow_up_to_id=follow_up_to_id,
        )
        self.db.add(row)
        self.db.flush()
        return row

    @tool("save_answer")
    def save_answer(
        self,
        interview_id: str,
        question_id: str,
        answer_text: str,
        time_taken_seconds: int | None = None,
    ) -> Answer:
        self._owned_interview(interview_id)
        question = self.db.get(InterviewQuestion, question_id)
        if question is None or question.interview_id != interview_id:
            raise ToolError("Question not found in this interview")
        if question.answer is not None:
            raise ToolError("This question has already been answered")

        row = Answer(
            interview_id=interview_id,
            question_id=question_id,
            answer_text=answer_text.strip(),
            time_taken_seconds=time_taken_seconds,
        )
        self.db.add(row)
        self.db.flush()
        return row

    @tool("save_interview_result")
    def save_evaluation(
        self, interview_id: str, answer_id: str, evaluation: AnswerEvaluation
    ) -> Evaluation:
        self._owned_interview(interview_id)
        row = Evaluation(
            interview_id=interview_id,
            answer_id=answer_id,
            score=evaluation.score,
            correctness=evaluation.correctness,
            relevance=evaluation.relevance,
            clarity=evaluation.clarity,
            completeness=evaluation.completeness,
            communication=evaluation.communication,
            quality=evaluation.quality.value,
            strengths=evaluation.strengths,
            weaknesses=evaluation.weaknesses,
            suggestions=evaluation.suggestions,
            missed_points=evaluation.missed_points,
            rationale=evaluation.rationale,
            generated_by=self.llm.name,
        )
        self.db.add(row)
        self.db.flush()
        return row

    @tool("save_improvement_plan")
    def save_improvement_plan(
        self, interview_id: str, plan: ImprovementPlanOutput
    ) -> ImprovementPlan:
        interview = self._owned_interview(interview_id)
        existing = self.db.execute(
            select(ImprovementPlan).where(ImprovementPlan.interview_id == interview_id)
        ).scalar_one_or_none()

        payload = {
            "weak_topics": plan.weak_topics,
            "recommended_concepts": plan.recommended_concepts,
            "daily_plan": [item.model_dump() for item in plan.daily_plan],
            "coding_questions": [q.model_dump(mode="json") for q in plan.coding_questions],
            "project_suggestions": plan.project_suggestions,
            "resources": [r.model_dump() for r in plan.resources],
            "overview": plan.overview,
            "generated_by": self.llm.name,
        }

        if existing is not None:
            for key, value in payload.items():
                setattr(existing, key, value)
            self.db.flush()
            return existing

        row = ImprovementPlan(
            interview_id=interview_id, user_id=interview.user_id, **payload
        )
        self.db.add(row)
        self.db.flush()
        return row


def topic_keywords(text: str, limit: int = 6) -> list[str]:
    """Distinctive keywords from a piece of text, used for topic labelling."""
    seen: dict[str, int] = {}
    for token in tokenize(text):
        if len(token) > 4:
            seen[token] = seen.get(token, 0) + 1
    return [word for word, _ in sorted(seen.items(), key=lambda p: -p[1])][:limit]

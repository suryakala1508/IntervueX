"""Interview lifecycle: start, answer a turn, complete, read history."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.llm import LLMError
from app.ai.tools import ToolError, ToolRunner
from app.ai.workflow import run_answer_turn, run_start_interview
from app.models.enums import Difficulty, InterviewStatus
from app.models.interview import (
    Evaluation,
    ImprovementPlan,
    Interview,
    InterviewQuestion,
)
from app.models.user import User
from app.schemas.interview import AnswerSubmit, InterviewCreate

logger = logging.getLogger(__name__)


def _ai_unavailable(exc: Exception) -> HTTPException:
    logger.exception("AI step failed")
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"The interview engine could not complete this step: {exc}",
    )


def get_owned_interview(db: Session, user_id: str, interview_id: str) -> Interview:
    interview = db.execute(
        select(Interview)
        .where(Interview.id == interview_id)
        .options(
            selectinload(Interview.questions).selectinload(InterviewQuestion.answer),
            selectinload(Interview.improvement_plan),
        )
    ).scalar_one_or_none()
    if interview is None or interview.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found"
        )
    return interview


def list_interviews(db: Session, user_id: str) -> list[Interview]:
    return list(
        db.execute(
            select(Interview)
            .where(Interview.user_id == user_id)
            .order_by(Interview.created_at.desc())
        ).scalars()
    )


def current_question(interview: Interview) -> InterviewQuestion | None:
    """The highest-positioned question that has not yet been answered."""
    unanswered = [q for q in interview.questions if q.answer is None]
    if not unanswered:
        return None
    return max(unanswered, key=lambda q: q.position)


def start_interview(
    db: Session, user: User, payload: InterviewCreate
) -> tuple[Interview, InterviewQuestion, list[str]]:
    job_id = payload.job_description_id
    if job_id:
        from app.services.profile import get_owned_job

        get_owned_job(db, user.id, job_id)

    interview = Interview(
        user_id=user.id,
        job_description_id=job_id,
        title=payload.title or "Practice interview",
        planned_question_count=payload.question_count,
        current_difficulty=payload.starting_difficulty.value,
        status=InterviewStatus.IN_PROGRESS.value,
    )
    db.add(interview)
    db.flush()

    runner = ToolRunner(db, user.id, interview_id=interview.id)
    try:
        result = run_start_interview(runner, interview.id)
    except (LLMError, ToolError) as exc:
        db.rollback()
        raise _ai_unavailable(exc) from exc

    db.commit()
    db.refresh(interview)

    question = db.get(InterviewQuestion, result["next_question_id"])
    assert question is not None
    return interview, question, list(result.get("events", []))


def assert_answerable(
    interview: Interview, question_id: str, db: Session
) -> InterviewQuestion:
    """Validate that this question can be answered right now.

    Called before the work starts by both the REST and SSE endpoints, so an
    invalid request is a plain HTTP error rather than an error delivered inside
    an already-committed 200 response.
    """
    if interview.status != InterviewStatus.IN_PROGRESS.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This interview is {interview.status} and no longer accepts answers",
        )

    question = db.get(InterviewQuestion, question_id)
    if question is None or question.interview_id != interview.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That question does not belong to this interview",
        )
    if question.answer is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This question has already been answered",
        )
    return question


def turn_result(db: Session, interview_id: str, state: dict) -> dict:
    """Shape a finished workflow state into the turn response payload."""
    evaluation = db.execute(
        select(Evaluation).where(Evaluation.answer_id == state["answer_id"])
    ).scalar_one()
    next_question = (
        db.get(InterviewQuestion, state["next_question_id"])
        if state.get("next_question_id")
        else None
    )
    return {
        "interview_id": interview_id,
        "evaluation": evaluation,
        "next_question": next_question,
        "finished": bool(state.get("finished")),
        "progress": state.get("progress", {}),
        "workflow_events": list(state.get("events", [])),
    }


def submit_answer(
    db: Session, user: User, interview_id: str, payload: AnswerSubmit
) -> dict:
    interview = get_owned_interview(db, user.id, interview_id)
    assert_answerable(interview, payload.question_id, db)

    runner = ToolRunner(db, user.id, interview_id=interview_id)
    try:
        result = run_answer_turn(
            runner,
            interview_id=interview_id,
            question_id=payload.question_id,
            answer_text=payload.answer_text,
            time_taken_seconds=payload.time_taken_seconds,
        )
    except (LLMError, ToolError) as exc:
        db.rollback()
        raise _ai_unavailable(exc) from exc

    db.commit()
    return turn_result(db, interview_id, dict(result))


def complete_interview(
    db: Session, user: User, interview_id: str
) -> tuple[Interview, ImprovementPlan]:
    """Finish the interview (if still running) and build the improvement plan."""
    interview = get_owned_interview(db, user.id, interview_id)

    answered = [q for q in interview.questions if q.answer is not None]
    if not answered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Answer at least one question before completing the interview",
        )

    scores = [
        q.answer.evaluation.score
        for q in answered
        if q.answer is not None and q.answer.evaluation is not None
    ]
    overall = round(sum(scores) / len(scores), 2) if scores else 0.0

    # Average score per topic, used to pick what the plan should target.
    by_topic: dict[str, list[int]] = {}
    transcript_parts: list[str] = []
    for question in sorted(answered, key=lambda q: q.position):
        answer = question.answer
        evaluation = answer.evaluation if answer else None
        if evaluation is not None:
            by_topic.setdefault(question.topic, []).append(evaluation.score)
        transcript_parts.append(
            f"Q{question.position} [{question.category}/{question.difficulty}] "
            f"({question.topic})\n{question.question_text}\n"
            f"ANSWER: {(answer.answer_text if answer else '')[:1200]}\n"
            f"SCORE: {evaluation.score if evaluation else 'n/a'}/10 "
            f"({evaluation.quality if evaluation else 'n/a'})\n"
        )

    topic_scores = [
        (topic, round(sum(values) / len(values), 2)) for topic, values in by_topic.items()
    ]

    runner = ToolRunner(db, user.id, interview_id=interview_id)
    try:
        ctx = runner.build_context(job_id=interview.job_description_id)
        plan_output = runner.create_improvement_plan(
            ctx=ctx,
            transcript="\n".join(transcript_parts),
            overall_score=overall,
            topic_scores=topic_scores,
        )
        plan = runner.save_improvement_plan(interview_id=interview_id, plan=plan_output)
    except (LLMError, ToolError) as exc:
        db.rollback()
        raise _ai_unavailable(exc) from exc

    interview.status = InterviewStatus.COMPLETED.value
    interview.overall_score = overall
    interview.summary = plan_output.overview
    db.commit()
    db.refresh(interview)
    db.refresh(plan)
    return interview, plan


def abandon_interview(db: Session, user: User, interview_id: str) -> Interview:
    interview = get_owned_interview(db, user.id, interview_id)
    if interview.status == InterviewStatus.IN_PROGRESS.value:
        interview.status = InterviewStatus.ABANDONED.value
        db.commit()
        db.refresh(interview)
    return interview


def build_detail(interview: Interview) -> dict:
    turns = [
        {"question": question, "answer": question.answer}
        for question in sorted(interview.questions, key=lambda q: q.position)
    ]
    return {
        **{
            field: getattr(interview, field)
            for field in (
                "id",
                "title",
                "status",
                "job_description_id",
                "planned_question_count",
                "current_difficulty",
                "overall_score",
                "summary",
                "created_at",
                "updated_at",
            )
        },
        "turns": turns,
        "current_question": current_question(interview),
        "improvement_plan": interview.improvement_plan,
    }


def get_plan(db: Session, user: User, interview_id: str) -> ImprovementPlan:
    interview = get_owned_interview(db, user.id, interview_id)
    if interview.improvement_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No improvement plan yet. Complete the interview to generate one."
            ),
        )
    return interview.improvement_plan


def delete_interview(db: Session, user: User, interview_id: str) -> None:
    interview = get_owned_interview(db, user.id, interview_id)
    db.delete(interview)
    db.commit()


def starting_difficulty_default() -> Difficulty:
    return Difficulty.MEDIUM

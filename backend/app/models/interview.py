"""Interview session, questions, answers, evaluations, and improvement plans."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey
from app.models.enums import Difficulty, InterviewStatus

if TYPE_CHECKING:
    from app.models.user import User


class Interview(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "interviews"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_description_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("job_descriptions.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), default="Practice interview")
    status: Mapped[str] = mapped_column(
        String(32), default=InterviewStatus.IN_PROGRESS.value, nullable=False
    )
    planned_question_count: Mapped[int] = mapped_column(Integer, default=8)
    current_difficulty: Mapped[str] = mapped_column(
        String(16), default=Difficulty.MEDIUM.value
    )
    overall_score: Mapped[float | None] = mapped_column(Float)
    # Snapshot of the grounded context used to start the interview, so results
    # remain reproducible even if the profile or job description changes later.
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    summary: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="interviews")
    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.position",
    )
    improvement_plan: Mapped["ImprovementPlan | None"] = relationship(
        back_populates="interview", uselist=False, cascade="all, delete-orphan"
    )


class InterviewQuestion(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "interview_questions"

    interview_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), default="general")
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    expected_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Chunk ids the question was grounded in, for traceability.
    source_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Set when this question was generated as a follow-up to a previous answer.
    follow_up_to_id: Mapped[str | None] = mapped_column(String(36))

    interview: Mapped["Interview"] = relationship(back_populates="questions")
    answer: Mapped["Answer | None"] = relationship(
        back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


class Answer(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "answers"

    question_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("interview_questions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    interview_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer)

    question: Mapped["InterviewQuestion"] = relationship(back_populates="answer")
    evaluation: Mapped["Evaluation | None"] = relationship(
        back_populates="answer", uselist=False, cascade="all, delete-orphan"
    )


class Evaluation(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "evaluations"

    answer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("answers.id", ondelete="CASCADE"), unique=True, index=True
    )
    interview_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )

    score: Mapped[int] = mapped_column(Integer, nullable=False)
    correctness: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance: Mapped[int] = mapped_column(Integer, nullable=False)
    clarity: Mapped[int] = mapped_column(Integer, nullable=False)
    completeness: Mapped[int] = mapped_column(Integer, nullable=False)
    communication: Mapped[int] = mapped_column(Integer, nullable=False)

    quality: Mapped[str] = mapped_column(String(16), nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, default=list)
    suggestions: Mapped[list[str]] = mapped_column(JSON, default=list)
    missed_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    rationale: Mapped[str | None] = mapped_column(Text)
    # "anthropic" or "offline" - makes it obvious which results came from a real model.
    generated_by: Mapped[str] = mapped_column(String(32), default="offline")

    answer: Mapped["Answer"] = relationship(back_populates="evaluation")


class ImprovementPlan(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "improvement_plans"

    interview_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    weak_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommended_concepts: Mapped[list[str]] = mapped_column(JSON, default=list)
    daily_plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    coding_questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    project_suggestions: Mapped[list[str]] = mapped_column(JSON, default=list)
    resources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    overview: Mapped[str | None] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(String(32), default="offline")

    interview: Mapped["Interview"] = relationship(back_populates="improvement_plan")


class ToolLog(Base, UUIDPrimaryKey, TimestampMixin):
    """Audit trail of every AI tool invocation.

    The agent workflow never touches the database directly - it calls the
    validated tool functions in app.ai.tools, each of which writes a row here.
    """

    __tablename__ = "tool_logs"

    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    interview_id: Mapped[str | None] = mapped_column(String(36), index=True)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_summary: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

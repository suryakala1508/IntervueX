"""Interview, answer, evaluation, plan, and dashboard schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    AnswerQuality,
    Difficulty,
    InterviewStatus,
    QuestionCategory,
)
from app.schemas.common import ORMModel


class InterviewCreate(BaseModel):
    job_description_id: str | None = None
    title: str | None = Field(default=None, max_length=255)
    question_count: int = Field(default=8, ge=3, le=20)
    starting_difficulty: Difficulty = Difficulty.MEDIUM


class QuestionOut(ORMModel):
    id: str
    position: int
    category: QuestionCategory
    difficulty: Difficulty
    topic: str
    question_text: str
    expected_points: list[str]
    follow_up_to_id: str | None
    created_at: datetime


class EvaluationOut(ORMModel):
    id: str
    score: int
    correctness: int
    relevance: int
    clarity: int
    completeness: int
    communication: int
    quality: AnswerQuality
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]
    missed_points: list[str]
    rationale: str | None
    generated_by: str


class AnswerOut(ORMModel):
    id: str
    question_id: str
    answer_text: str
    time_taken_seconds: int | None
    created_at: datetime
    evaluation: EvaluationOut | None


class AnswerSubmit(BaseModel):
    question_id: str
    answer_text: str = Field(min_length=1, max_length=20000)
    time_taken_seconds: int | None = Field(default=None, ge=0, le=86400)


class TurnResponse(BaseModel):
    """What the client needs to render the next screen after an answer."""

    interview_id: str
    evaluation: EvaluationOut
    next_question: QuestionOut | None
    finished: bool
    progress: dict[str, Any]
    workflow_events: list[str]


class InterviewOut(ORMModel):
    id: str
    title: str
    status: InterviewStatus
    job_description_id: str | None
    planned_question_count: int
    current_difficulty: Difficulty
    overall_score: float | None
    summary: str | None
    created_at: datetime
    updated_at: datetime


class InterviewTurn(BaseModel):
    question: QuestionOut
    answer: AnswerOut | None


class InterviewDetail(InterviewOut):
    turns: list[InterviewTurn]
    current_question: QuestionOut | None
    improvement_plan: "ImprovementPlanOut | None" = None


class StartInterviewResponse(BaseModel):
    interview: InterviewOut
    first_question: QuestionOut
    workflow_events: list[str]


class ImprovementPlanOut(ORMModel):
    id: str
    interview_id: str
    overview: str | None
    weak_topics: list[str]
    recommended_concepts: list[str]
    daily_plan: list[dict[str, Any]]
    coding_questions: list[dict[str, Any]]
    project_suggestions: list[str]
    resources: list[dict[str, Any]]
    generated_by: str
    created_at: datetime


class CompleteInterviewResponse(BaseModel):
    interview: InterviewOut
    improvement_plan: ImprovementPlanOut


# -- dashboard -------------------------------------------------------------- #


class TopicPerformance(BaseModel):
    topic: str
    average_score: float
    answer_count: int


class ScorePoint(BaseModel):
    interview_id: str
    completed_at: datetime
    score: float


class RubricAverages(BaseModel):
    correctness: float
    relevance: float
    clarity: float
    completeness: float
    communication: float


class DashboardResponse(BaseModel):
    total_interviews: int
    completed_interviews: int
    total_answers: int
    average_score: float | None
    best_score: float | None
    rubric_averages: RubricAverages | None
    strongest_topics: list[TopicPerformance]
    weak_topics: list[TopicPerformance]
    progress: list[ScorePoint]
    recent_interviews: list[InterviewOut]
    latest_plan: ImprovementPlanOut | None


InterviewDetail.model_rebuild()

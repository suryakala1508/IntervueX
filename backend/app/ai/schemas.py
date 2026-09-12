"""Pydantic schemas that constrain every LLM output.

These are passed to `client.messages.parse(output_format=...)`, so the model is
constrained to emit conforming JSON and the result is validated before it ever
reaches the database.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import AnswerQuality, Difficulty, QuestionCategory


class GeneratedQuestion(BaseModel):
    """A single interview question grounded in the retrieved context."""

    question_text: str = Field(
        description="The interview question, addressed directly to the candidate."
    )
    category: QuestionCategory
    difficulty: Difficulty
    topic: str = Field(
        description="Short topic label, e.g. 'SQL indexing' or 'REST API design'.",
        max_length=120,
    )
    expected_points: list[str] = Field(
        default_factory=list,
        description="3-5 key points a complete answer should cover.",
    )


class GeneratedQuestionSet(BaseModel):
    questions: list[GeneratedQuestion]


class AnswerEvaluation(BaseModel):
    """Rubric-based evaluation of one candidate answer."""

    score: int = Field(ge=0, le=10, description="Overall score.")
    correctness: int = Field(ge=0, le=10)
    relevance: int = Field(ge=0, le=10)
    clarity: int = Field(ge=0, le=10)
    completeness: int = Field(ge=0, le=10)
    communication: int = Field(ge=0, le=10)
    quality: AnswerQuality = Field(
        description=(
            "strong = confident and complete; adequate = correct but shallow; "
            "weak = largely incorrect; incomplete = trailed off or did not "
            "address the question."
        )
    )
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    missed_points: list[str] = Field(
        default_factory=list,
        description="Expected points the answer did not cover.",
    )
    rationale: str = Field(default="", description="One or two sentences of reasoning.")


class DailyPlanItem(BaseModel):
    day: int = Field(ge=1, le=30)
    focus: str
    activities: list[str] = Field(default_factory=list)
    estimated_minutes: int = Field(default=60, ge=15, le=480)


class CodingQuestionSuggestion(BaseModel):
    title: str
    topic: str
    difficulty: Difficulty
    why: str = Field(default="", description="Why this is relevant to the candidate.")


class ResourceSuggestion(BaseModel):
    title: str
    kind: str = Field(description="e.g. 'documentation', 'course', 'book', 'article'.")
    detail: str = Field(default="", description="What to read or watch, and why.")


class ImprovementPlanOutput(BaseModel):
    """The post-interview coaching plan."""

    overview: str = Field(description="Two or three sentences summarising performance.")
    weak_topics: list[str] = Field(default_factory=list)
    recommended_concepts: list[str] = Field(default_factory=list)
    daily_plan: list[DailyPlanItem] = Field(default_factory=list)
    coding_questions: list[CodingQuestionSuggestion] = Field(default_factory=list)
    project_suggestions: list[str] = Field(default_factory=list)
    resources: list[ResourceSuggestion] = Field(default_factory=list)


class ParsedResumeProfile(BaseModel):
    """Structured fields extracted from an uploaded resume."""

    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    years_of_experience: float | None = Field(default=None, ge=0, le=60)
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    summary: str | None = None


class ParsedJobDescription(BaseModel):
    """Structured fields extracted from a pasted or uploaded job description."""

    title: str
    company: str | None = None
    seniority: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)

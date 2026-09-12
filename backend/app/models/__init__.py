"""ORM models. Importing this package registers every table on Base.metadata."""

from app.db.base_class import Base
from app.models.document import Document, DocumentChunk, JobDescription
from app.models.enums import (
    AnswerQuality,
    Difficulty,
    DocumentType,
    InterviewStatus,
    QuestionCategory,
    UserRole,
)
from app.models.interview import (
    Answer,
    Evaluation,
    ImprovementPlan,
    Interview,
    InterviewQuestion,
    ToolLog,
)
from app.models.user import CandidateProfile, User

__all__ = [
    "Base",
    "User",
    "CandidateProfile",
    "Document",
    "DocumentChunk",
    "JobDescription",
    "Interview",
    "InterviewQuestion",
    "Answer",
    "Evaluation",
    "ImprovementPlan",
    "ToolLog",
    "UserRole",
    "DocumentType",
    "InterviewStatus",
    "QuestionCategory",
    "Difficulty",
    "AnswerQuality",
]

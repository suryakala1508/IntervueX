"""Shared enumerations, stored as plain strings for portability."""

from enum import StrEnum


class UserRole(StrEnum):
    CANDIDATE = "candidate"
    ADMIN = "admin"


class DocumentType(StrEnum):
    RESUME = "resume"
    JOB_DESCRIPTION = "job_description"
    OTHER = "other"


class InterviewStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class QuestionCategory(StrEnum):
    TECHNICAL = "technical"
    PROJECT = "project"
    BEHAVIORAL = "behavioral"
    ROLE_SPECIFIC = "role_specific"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

    @property
    def rank(self) -> int:
        return {"easy": 0, "medium": 1, "hard": 2}[self.value]

    @classmethod
    def from_rank(cls, rank: int) -> "Difficulty":
        clamped = max(0, min(2, rank))
        return [cls.EASY, cls.MEDIUM, cls.HARD][clamped]


class AnswerQuality(StrEnum):
    """The adaptive signal derived from an evaluation."""

    STRONG = "strong"
    ADEQUATE = "adequate"
    WEAK = "weak"
    INCOMPLETE = "incomplete"

"""User account and candidate profile."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.document import Document, JobDescription
    from app.models.interview import Interview


class User(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), default=UserRole.CANDIDATE.value, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profile: Mapped["CandidateProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    job_descriptions: Mapped[list["JobDescription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value


class CandidateProfile(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "candidate_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    headline: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    years_of_experience: Mapped[float | None] = mapped_column()

    # Free-form structured sections. JSON (not JSONB) keeps the model portable to
    # SQLite for the test suite.
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    projects: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    certifications: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    preferred_role: Mapped[str | None] = mapped_column(String(255))
    target_company: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)

    resume_document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="SET NULL")
    )

    user: Mapped["User"] = relationship(back_populates="profile")
    resume: Mapped["Document | None"] = relationship(
        foreign_keys=[resume_document_id], post_update=True
    )

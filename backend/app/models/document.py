"""Uploaded documents, their embedded chunks, and target job descriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey
from app.db.vector import EmbeddingColumn
from app.models.enums import DocumentType

if TYPE_CHECKING:
    from app.models.user import User


class Document(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "documents"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), default="application/pdf")
    doc_type: Mapped[str] = mapped_column(
        String(32), default=DocumentType.OTHER.value, nullable=False
    )
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    extracted_text: Mapped[str] = mapped_column(Text, default="")

    user: Mapped["User"] = relationship(
        back_populates="documents", foreign_keys=[user_id]
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_user_doc", "user_id", "document_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=0)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # pgvector `vector` column in production, JSON list in the portable fallback.
    embedding: Mapped[list[float]] = mapped_column(EmbeddingColumn, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class JobDescription(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "job_descriptions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255))
    seniority: Mapped[str | None] = mapped_column(String(64))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="job_descriptions")

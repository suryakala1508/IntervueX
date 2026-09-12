"""Declarative base and shared column helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base for all ORM models.

    IDs are stored as 36-character UUID strings rather than a native UUID type so
    that the same models run unchanged on PostgreSQL (production) and SQLite
    (tests), which is what lets the test suite run with no infrastructure.
    """


class UUIDPrimaryKey:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

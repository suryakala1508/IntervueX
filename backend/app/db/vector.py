"""Vector-column backend selection and similarity search.

pgvector is the intended production backend. It is not always available (a plain
Homebrew PostgreSQL build, or SQLite under test), so the embedding column type is
resolved once at import time and retrieval has a portable fallback that computes
cosine similarity in Python.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from sqlalchemy import JSON, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import engine

logger = logging.getLogger(__name__)


def _pgvector_is_available() -> bool:
    """True when the connected database can provide the `vector` extension."""
    if not settings.database_url.startswith("postgresql"):
        return False
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
            ).first()
            return row is not None
    except SQLAlchemyError as exc:
        # The database may simply not be up yet (e.g. building an image). Trust
        # the configured default rather than silently downgrading.
        logger.warning(
            "Could not probe for pgvector (%s); assuming it is available. "
            "Set VECTOR_BACKEND=fallback to override.",
            exc.__class__.__name__,
        )
        return True


def _resolve_backend() -> str:
    if settings.vector_backend != "auto":
        return settings.vector_backend
    return "pgvector" if _pgvector_is_available() else "fallback"


VECTOR_BACKEND: str = _resolve_backend()
USING_PGVECTOR: bool = VECTOR_BACKEND == "pgvector"

if USING_PGVECTOR:
    from pgvector.sqlalchemy import Vector

    EmbeddingColumn: Any = Vector(settings.embedding_dim)
else:
    EmbeddingColumn = JSON

logger.info("Vector backend: %s", VECTOR_BACKEND)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either is degenerate."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)

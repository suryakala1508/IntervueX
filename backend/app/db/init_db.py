"""Schema creation and the pgvector extension."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine
from app.db.vector import USING_PGVECTOR
from app.models import Base  # noqa: F401 - registers every table

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Create the vector extension (if applicable) and all tables.

    `create_all` is enough for this project's lifecycle; Alembic is wired up for
    real migrations once the schema needs to change in production.
    """
    if USING_PGVECTOR:
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except SQLAlchemyError:
            logger.exception(
                "Could not create the pgvector extension. The database user may "
                "lack privileges; set VECTOR_BACKEND=fallback to run without it."
            )
            raise

    Base.metadata.create_all(bind=engine)
    logger.info("Database schema is up to date")

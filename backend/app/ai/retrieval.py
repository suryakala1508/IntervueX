"""Vector retrieval over a user's document chunks.

Uses pgvector's cosine distance operator when available, and otherwise fetches
the user's chunks and ranks them in Python. Both paths are scoped to the calling
user's own chunks - retrieval is never cross-tenant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedding_provider
from app.db.vector import USING_PGVECTOR, cosine_similarity
from app.models.document import DocumentChunk

logger = logging.getLogger(__name__)

# Chunks below this cosine similarity add noise rather than grounding.
MIN_SIMILARITY = 0.05


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    doc_type: str
    page_number: int
    chunk_index: int
    content: str
    score: float


def search_chunks(
    db: Session,
    *,
    user_id: str,
    query: str,
    doc_type: str | None = None,
    limit: int = 6,
) -> list[RetrievedChunk]:
    """Return the user's chunks most similar to `query`, best first."""
    if not query.strip():
        return []

    provider = get_embedding_provider()
    query_vector = provider.embed_one(query, input_type="query")

    stmt = select(DocumentChunk).where(DocumentChunk.user_id == user_id)
    if doc_type:
        stmt = stmt.where(DocumentChunk.doc_type == doc_type)

    if USING_PGVECTOR:
        # cosine_distance = 1 - cosine_similarity; ordering ascending gives the
        # most similar first, and the database does the work.
        stmt = stmt.order_by(
            DocumentChunk.embedding.cosine_distance(query_vector)
        ).limit(limit)
        rows = db.execute(stmt).scalars().all()
        results = [
            RetrievedChunk(
                chunk_id=row.id,
                document_id=row.document_id,
                doc_type=row.doc_type,
                page_number=row.page_number,
                chunk_index=row.chunk_index,
                content=row.content,
                score=cosine_similarity(list(row.embedding or []), query_vector),
            )
            for row in rows
        ]
    else:
        rows = db.execute(stmt).scalars().all()
        results = [
            RetrievedChunk(
                chunk_id=row.id,
                document_id=row.document_id,
                doc_type=row.doc_type,
                page_number=row.page_number,
                chunk_index=row.chunk_index,
                content=row.content,
                score=cosine_similarity(list(row.embedding or []), query_vector),
            )
            for row in rows
        ]
        results.sort(key=lambda chunk: chunk.score, reverse=True)
        results = results[:limit]

    return [chunk for chunk in results if chunk.score >= MIN_SIMILARITY]

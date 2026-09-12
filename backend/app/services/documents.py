"""Document ingestion: extract -> clean -> chunk -> embed -> store."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedding_provider
from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.models.enums import DocumentType
from app.utils.text import (
    DocumentParseError,
    chunk_text,
    clean_text,
    extract_pdf_pages,
    page_for_offset,
)

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/octet-stream",  # some browsers send this for .pdf
}


def _pages_from_upload(data: bytes, filename: str, content_type: str) -> list[str]:
    is_pdf = filename.lower().endswith(".pdf") or content_type == "application/pdf"
    if is_pdf:
        return extract_pdf_pages(data)
    try:
        return [clean_text(data.decode("utf-8"))]
    except UnicodeDecodeError as exc:
        raise DocumentParseError(
            "The file is not a PDF and is not valid UTF-8 text"
        ) from exc


def ingest_document(
    db: Session,
    *,
    user_id: str,
    data: bytes,
    filename: str,
    content_type: str,
    doc_type: DocumentType,
) -> Document:
    """Store a document and its embedded chunks. Commits on success."""
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty"
        )
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit"
            ),
        )
    if content_type not in ALLOWED_CONTENT_TYPES and not filename.lower().endswith(
        (".pdf", ".txt", ".md")
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a PDF or a plain-text file",
        )

    try:
        pages = _pages_from_upload(data, filename, content_type)
    except DocumentParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    full_text = "\n\n".join(pages).strip()
    if not full_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No text could be extracted. If this is a scanned PDF, it needs OCR "
                "before it can be used."
            ),
        )

    document = Document(
        user_id=user_id,
        filename=filename[:512],
        content_type=content_type[:128],
        doc_type=doc_type.value,
        page_count=len(pages),
        char_count=len(full_text),
        extracted_text=full_text,
    )
    db.add(document)
    db.flush()

    chunks = chunk_text(
        full_text, settings.chunk_size_chars, settings.chunk_overlap_chars
    )
    if chunks:
        provider = get_embedding_provider()
        vectors = provider.embed(chunks, input_type="document")
        # Page separators were joined with "\n\n"; account for them when mapping
        # a chunk offset back to its source page.
        page_lengths = [len(page) + 2 for page in pages]

        cursor = 0
        for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
            offset = full_text.find(chunk, cursor)
            if offset == -1:
                offset = cursor
            cursor = offset + max(1, len(chunk) - settings.chunk_overlap_chars)
            db.add(
                DocumentChunk(
                    user_id=user_id,
                    document_id=document.id,
                    doc_type=doc_type.value,
                    page_number=page_for_offset(page_lengths, offset),
                    chunk_index=index,
                    content=chunk,
                    embedding=vector,
                )
            )

    document.chunk_count = len(chunks)
    db.commit()
    db.refresh(document)
    logger.info(
        "Ingested %s (%s): %d pages, %d chunks",
        document.filename,
        doc_type.value,
        document.page_count,
        document.chunk_count,
    )
    return document


def list_documents(db: Session, user_id: str) -> list[Document]:
    return list(
        db.execute(
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
        ).scalars()
    )


def get_owned_document(db: Session, user_id: str, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return document


def delete_document(db: Session, user_id: str, document_id: str) -> None:
    document = get_owned_document(db, user_id, document_id)
    db.delete(document)
    db.commit()

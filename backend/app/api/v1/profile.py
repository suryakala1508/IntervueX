"""Candidate profile, documents, and job description endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.ai.tools import ToolRunner
from app.api.deps import CurrentUser, DbSession
from app.models.enums import DocumentType
from app.schemas.common import Message
from app.schemas.profile import (
    ChunkOut,
    DocumentOut,
    JobDescriptionCreate,
    JobDescriptionOut,
    ProfileOut,
    ProfileUpdate,
    ResumeUploadResponse,
    SearchResponse,
)
from app.services import documents as doc_service
from app.services import profile as profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def read_profile(user: CurrentUser, db: DbSession) -> ProfileOut:
    return ProfileOut.model_validate(
        profile_service.get_or_create_profile(db, user.id)
    )


@router.put("", response_model=ProfileOut)
def update_profile(
    payload: ProfileUpdate, user: CurrentUser, db: DbSession
) -> ProfileOut:
    return ProfileOut.model_validate(
        profile_service.update_profile(db, user.id, payload)
    )


@router.post(
    "/resume", response_model=ResumeUploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_resume(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File(description="PDF or text resume")],
) -> ResumeUploadResponse:
    data = await file.read()
    document = doc_service.ingest_document(
        db,
        user_id=user.id,
        data=data,
        filename=file.filename or "resume.pdf",
        content_type=file.content_type or "application/pdf",
        doc_type=DocumentType.RESUME,
    )
    profile, extracted = profile_service.apply_parsed_resume(db, user, document)
    return ResumeUploadResponse(
        document=DocumentOut.model_validate(document),
        profile=ProfileOut.model_validate(profile),
        extracted_fields=extracted,
    )


# --------------------------------------------------------------------------- #

documents_router = APIRouter(prefix="/documents", tags=["documents"])


@documents_router.post(
    "/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED
)
async def upload_document(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    doc_type: Annotated[DocumentType, Form()] = DocumentType.OTHER,
) -> DocumentOut:
    data = await file.read()
    document = doc_service.ingest_document(
        db,
        user_id=user.id,
        data=data,
        filename=file.filename or "document.pdf",
        content_type=file.content_type or "application/pdf",
        doc_type=doc_type,
    )
    return DocumentOut.model_validate(document)


@documents_router.get("", response_model=list[DocumentOut])
def list_documents(user: CurrentUser, db: DbSession) -> list[DocumentOut]:
    return [
        DocumentOut.model_validate(d) for d in doc_service.list_documents(db, user.id)
    ]


@documents_router.delete("/{document_id}", response_model=Message)
def delete_document(document_id: str, user: CurrentUser, db: DbSession) -> Message:
    doc_service.delete_document(db, user.id, document_id)
    return Message(detail="Document deleted")


@documents_router.get("/search", response_model=SearchResponse)
def search_documents(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str, Query(min_length=2, max_length=500)],
    doc_type: DocumentType | None = None,
    limit: Annotated[int, Query(ge=1, le=25)] = 6,
) -> SearchResponse:
    """Inspect what the RAG layer retrieves for a query - useful for debugging."""
    runner = ToolRunner(db, user.id)
    chunks = runner.search_candidate_documents(
        query=q, doc_type=doc_type.value if doc_type else None, limit=limit
    )
    return SearchResponse(
        query=q, results=[ChunkOut(**chunk.__dict__) for chunk in chunks]
    )


# --------------------------------------------------------------------------- #

jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])


@jobs_router.post(
    "", response_model=JobDescriptionOut, status_code=status.HTTP_201_CREATED
)
def create_job(
    payload: JobDescriptionCreate, user: CurrentUser, db: DbSession
) -> JobDescriptionOut:
    return JobDescriptionOut.model_validate(
        profile_service.create_job_description(db, user.id, payload)
    )


@jobs_router.post(
    "/upload", response_model=JobDescriptionOut, status_code=status.HTTP_201_CREATED
)
async def upload_job(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    company: Annotated[str | None, Form()] = None,
    set_active: Annotated[bool, Form()] = True,
) -> JobDescriptionOut:
    data = await file.read()
    document = doc_service.ingest_document(
        db,
        user_id=user.id,
        data=data,
        filename=file.filename or "job.pdf",
        content_type=file.content_type or "application/pdf",
        doc_type=DocumentType.JOB_DESCRIPTION,
    )
    job = profile_service.create_job_description(
        db,
        user.id,
        JobDescriptionCreate(
            title=title,
            company=company,
            raw_text=document.extracted_text,
            set_active=set_active,
        ),
        source_document_id=document.id,
    )
    return JobDescriptionOut.model_validate(job)


@jobs_router.get("", response_model=list[JobDescriptionOut])
def list_jobs(user: CurrentUser, db: DbSession) -> list[JobDescriptionOut]:
    return [
        JobDescriptionOut.model_validate(j)
        for j in profile_service.list_job_descriptions(db, user.id)
    ]


@jobs_router.get("/{job_id}", response_model=JobDescriptionOut)
def read_job(job_id: str, user: CurrentUser, db: DbSession) -> JobDescriptionOut:
    return JobDescriptionOut.model_validate(
        profile_service.get_owned_job(db, user.id, job_id)
    )


@jobs_router.post("/{job_id}/activate", response_model=JobDescriptionOut)
def activate_job(job_id: str, user: CurrentUser, db: DbSession) -> JobDescriptionOut:
    return JobDescriptionOut.model_validate(
        profile_service.activate_job(db, user.id, job_id)
    )

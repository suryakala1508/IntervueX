"""Candidate profile, document, and job description schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import DocumentType
from app.schemas.common import ORMModel


class ProfileUpdate(BaseModel):
    headline: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    years_of_experience: float | None = Field(default=None, ge=0, le=60)
    education: list[Any] | None = None
    skills: list[str] | None = None
    experience: list[Any] | None = None
    projects: list[Any] | None = None
    certifications: list[Any] | None = None
    preferred_role: str | None = Field(default=None, max_length=255)
    target_company: str | None = Field(default=None, max_length=255)
    summary: str | None = None


class ProfileOut(ORMModel):
    id: str
    user_id: str
    headline: str | None
    location: str | None
    years_of_experience: float | None
    education: list[Any]
    skills: list[str]
    experience: list[Any]
    projects: list[Any]
    certifications: list[Any]
    preferred_role: str | None
    target_company: str | None
    summary: str | None
    resume_document_id: str | None
    updated_at: datetime


class DocumentOut(ORMModel):
    id: str
    filename: str
    doc_type: DocumentType
    page_count: int
    char_count: int
    chunk_count: int
    created_at: datetime


class ResumeUploadResponse(BaseModel):
    document: DocumentOut
    profile: ProfileOut
    extracted_fields: dict[str, Any]


class JobDescriptionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    raw_text: str = Field(min_length=30, max_length=60000)
    set_active: bool = True


class JobDescriptionOut(ORMModel):
    id: str
    title: str
    company: str | None
    seniority: str | None
    raw_text: str
    is_active: bool
    source_document_id: str | None
    created_at: datetime


class ChunkOut(BaseModel):
    chunk_id: str
    document_id: str
    doc_type: str
    page_number: int
    chunk_index: int
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[ChunkOut]

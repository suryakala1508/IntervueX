"""Candidate profile and job description management."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm import LLMError, get_llm_provider
from app.models.document import Document, JobDescription
from app.models.enums import DocumentType
from app.models.user import CandidateProfile, User
from app.schemas.profile import JobDescriptionCreate, ProfileUpdate

logger = logging.getLogger(__name__)


def get_or_create_profile(db: Session, user_id: str) -> CandidateProfile:
    profile = db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    ).scalar_one_or_none()
    if profile is None:
        profile = CandidateProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(
    db: Session, user_id: str, payload: ProfileUpdate
) -> CandidateProfile:
    profile = get_or_create_profile(db, user_id)
    # exclude_unset means an omitted field is left alone, while an explicit null
    # clears it.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


def apply_parsed_resume(
    db: Session, user: User, document: Document
) -> tuple[CandidateProfile, dict]:
    """Extract structured fields from a resume and merge them into the profile.

    Merging is additive: existing user-entered values are never overwritten by
    the parser, and skills are unioned rather than replaced.
    """
    provider = get_llm_provider()
    try:
        parsed = provider.parse_resume(document.extracted_text)
    except LLMError as exc:
        logger.warning("Resume parsing failed (%s); storing the document only", exc)
        profile = get_or_create_profile(db, user.id)
        profile.resume_document_id = document.id
        db.commit()
        db.refresh(profile)
        return profile, {"parsed": False, "reason": str(exc)}

    profile = get_or_create_profile(db, user.id)
    profile.resume_document_id = document.id

    if parsed.headline and not profile.headline:
        profile.headline = parsed.headline[:255]
    if parsed.location and not profile.location:
        profile.location = parsed.location[:255]
    if parsed.years_of_experience is not None and profile.years_of_experience is None:
        profile.years_of_experience = parsed.years_of_experience
    if parsed.summary and not profile.summary:
        profile.summary = parsed.summary

    existing_skills = [str(s) for s in (profile.skills or [])]
    known = {s.lower() for s in existing_skills}
    merged = existing_skills + [
        s for s in parsed.skills if s.lower() not in known and s.strip()
    ]
    profile.skills = merged[:60]

    for field, values in (
        ("education", parsed.education),
        ("experience", parsed.experience),
        ("projects", parsed.projects),
        ("certifications", parsed.certifications),
    ):
        if values and not getattr(profile, field):
            setattr(profile, field, list(values))

    db.commit()
    db.refresh(profile)
    return profile, {"parsed": True, **parsed.model_dump()}


def create_job_description(
    db: Session,
    user_id: str,
    payload: JobDescriptionCreate,
    source_document_id: str | None = None,
) -> JobDescription:
    provider = get_llm_provider()
    title = payload.title
    company = payload.company
    seniority = None

    try:
        parsed = provider.parse_job_description(payload.raw_text)
        title = title or parsed.title
        company = company or parsed.company
        seniority = parsed.seniority
    except LLMError as exc:
        logger.warning("Job description parsing failed (%s); using raw values", exc)

    job = JobDescription(
        user_id=user_id,
        title=(title or "Untitled role")[:255],
        company=company[:255] if company else None,
        seniority=seniority[:64] if seniority else None,
        raw_text=payload.raw_text,
        source_document_id=source_document_id,
        is_active=payload.set_active,
    )
    db.add(job)
    db.flush()

    if payload.set_active:
        _deactivate_others(db, user_id, job.id)

    db.commit()
    db.refresh(job)
    return job


def _deactivate_others(db: Session, user_id: str, keep_id: str) -> None:
    others = db.execute(
        select(JobDescription).where(
            JobDescription.user_id == user_id,
            JobDescription.id != keep_id,
            JobDescription.is_active.is_(True),
        )
    ).scalars()
    for other in others:
        other.is_active = False


def list_job_descriptions(db: Session, user_id: str) -> list[JobDescription]:
    return list(
        db.execute(
            select(JobDescription)
            .where(JobDescription.user_id == user_id)
            .order_by(JobDescription.created_at.desc())
        ).scalars()
    )


def get_owned_job(db: Session, user_id: str, job_id: str) -> JobDescription:
    job = db.get(JobDescription, job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job description not found"
        )
    return job


def activate_job(db: Session, user_id: str, job_id: str) -> JobDescription:
    job = get_owned_job(db, user_id, job_id)
    job.is_active = True
    _deactivate_others(db, user_id, job.id)
    db.commit()
    db.refresh(job)
    return job


def resume_doc_type() -> DocumentType:
    return DocumentType.RESUME

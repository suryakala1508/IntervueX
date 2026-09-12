"""Registration, login, and token refresh."""

from __future__ import annotations

import jwt
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import CandidateProfile, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password",
)


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


def register_user(db: Session, payload: RegisterRequest) -> tuple[User, TokenPair]:
    email = _normalise_email(payload.email)
    existing = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.CANDIDATE.value,
    )
    db.add(user)
    db.flush()

    # Every candidate gets an empty profile so the UI has something to edit.
    db.add(CandidateProfile(user_id=user.id))
    db.commit()
    db.refresh(user)
    return user, _token_pair(user)


def authenticate(db: Session, payload: LoginRequest) -> tuple[User, TokenPair]:
    email = _normalise_email(payload.email)
    user = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalar_one_or_none()

    # Always run a hash comparison so a missing account and a wrong password
    # take comparable time.
    if user is None:
        verify_password(payload.password, hash_password("dummy-password"))
        raise INVALID_CREDENTIALS
    if not verify_password(payload.password, user.password_hash):
        raise INVALID_CREDENTIALS
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account is disabled"
        )
    return user, _token_pair(user)


def refresh_tokens(db: Session, refresh_token: str) -> TokenPair:
    try:
        payload = decode_token(refresh_token, "refresh")
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None

    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    return _token_pair(user)

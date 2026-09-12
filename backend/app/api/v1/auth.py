"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.schemas.common import Message
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterResponse(TokenPair):
    pass


@router.post(
    "/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED
)
def register(payload: RegisterRequest, db: DbSession) -> TokenPair:
    _, tokens = auth_service.register_user(db, payload)
    return tokens


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: DbSession) -> TokenPair:
    _, tokens = auth_service.authenticate(db, payload)
    return tokens


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    return auth_service.refresh_tokens(db, payload.refresh_token)


@router.post("/logout", response_model=Message)
def logout(_: CurrentUser) -> Message:
    # Tokens are stateless and short-lived, so logout is a client-side discard.
    # The endpoint exists so the client has a single place to call, and so that
    # adding server-side revocation later does not change the API surface.
    return Message(detail="Signed out. Discard your tokens.")


users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("/me", response_model=UserOut)
def read_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)

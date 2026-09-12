"""Shared response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    llm_provider: str
    llm_model: str | None
    embedding_provider: str
    vector_backend: str
    database_ok: bool

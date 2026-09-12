"""FastAPI application factory and entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.ai.embeddings import get_embedding_provider
from app.ai.llm import LLMError, get_llm_provider
from app.ai.tools import ToolError
from app.api.v1.router import api_router
from app.core.config import settings, validate_runtime_settings
from app.db.init_db import init_db
from app.db.session import engine
from app.db.vector import VECTOR_BACKEND
from app.schemas.common import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DESCRIPTION = """
IntervueX is an adaptive AI interview and assessment platform.

The flow is: build a candidate profile (optionally from a resume PDF), save a
target job description, then run an interview. Questions are grounded in the
candidate's own documents via retrieval, each answer is graded against a fixed
rubric, and the next question adapts to how the last one went.

Authenticate with `POST /api/v1/auth/login` and send the returned
`access_token` as `Authorization: Bearer <token>`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    validate_runtime_settings()
    init_db()
    # Resolving the providers at boot means a misconfigured key surfaces in the
    # startup logs rather than in the middle of someone's interview.
    logger.info(
        "Ready: llm=%s embeddings=%s vectors=%s",
        get_llm_provider().name,
        get_embedding_provider().name,
        VECTOR_BACKEND,
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ToolError)
    async def tool_error_handler(_: Request, exc: ToolError) -> JSONResponse:
        """A tool refused the call - bad arguments or a resource that isn't there."""
        logger.warning("Tool error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(LLMError)
    async def llm_error_handler(_: Request, exc: LLMError) -> JSONResponse:
        """The model was unreachable or returned something unusable."""
        logger.exception("LLM error")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"The interview engine is unavailable: {exc}"},
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": app.version,
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    def health() -> HealthResponse:
        """Liveness plus the resolved backends, for deployment smoke checks."""
        database_ok = True
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception("Health check could not reach the database")
            database_ok = False

        llm = get_llm_provider()
        return HealthResponse(
            status="ok" if database_ok else "degraded",
            environment=settings.environment,
            llm_provider=llm.name,
            # The offline provider has no model to report.
            llm_model=getattr(llm, "model", None),
            embedding_provider=get_embedding_provider().name,
            vector_backend=VECTOR_BACKEND,
            database_ok=database_ok,
        )

    return app


app = create_app()

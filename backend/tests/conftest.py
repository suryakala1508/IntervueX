"""Shared test fixtures.

The suite runs against a throwaway SQLite file and the deterministic offline AI
providers, so `pytest` needs no database server, no API keys, and no network.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Must be set before anything imports app.core.config, which caches Settings and
# resolves the vector backend at import time.
_DB_PATH = Path(__file__).parent / "_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["VECTOR_BACKEND"] = "fallback"
os.environ["LLM_PROVIDER"] = "offline"
os.environ["EMBEDDING_PROVIDER"] = "hashing"
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database() -> Iterator[None]:
    """Give every test an empty schema, so tests cannot leak state into each other."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Iterator[TestClient]:
    # No context manager: the lifespan would re-run init_db and the provider
    # probes on every test. The schema is handled by fresh_database.
    yield TestClient(app)


def register(client: TestClient, email: str = "candidate@example.com") -> dict[str, str]:
    """Register a user and return the Authorization header for them."""
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test Candidate", "password": "password123"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    return register(client)


SAMPLE_JOB = (
    "We are hiring a Backend Engineer. You will design and build REST APIs in "
    "Python with FastAPI, model data in PostgreSQL, and keep services fast under "
    "load. Requirements: strong Python, SQL and schema design, API design, "
    "testing discipline, and comfort with Docker."
)


@pytest.fixture
def ready_candidate(client: TestClient, auth: dict[str, str]) -> dict[str, str]:
    """A candidate with a filled-in profile and an active target job."""
    client.put(
        "/api/v1/profile",
        headers=auth,
        json={
            "headline": "Backend engineer",
            "years_of_experience": 2,
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "SQL"],
            "preferred_role": "Backend Engineer",
            "projects": [
                {
                    "name": "OrderFlow",
                    "description": "An order processing service in FastAPI and PostgreSQL",
                }
            ],
        },
    )
    client.post(
        "/api/v1/jobs",
        headers=auth,
        json={"title": "Backend Engineer", "raw_text": SAMPLE_JOB},
    )
    return auth

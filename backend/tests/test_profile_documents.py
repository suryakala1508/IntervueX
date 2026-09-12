"""Candidate profile, resume/document ingestion, and job descriptions."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.utils.text import chunk_text, clean_text, page_for_offset
from tests.conftest import SAMPLE_JOB, register

RESUME_TEXT = """Grace Hopper
Backend Engineer - Boston, MA

SUMMARY
Backend engineer with 4 years of experience building Python services.

SKILLS
Python, FastAPI, PostgreSQL, Docker, Redis, SQL

EXPERIENCE
Senior Engineer, Acme Corp (2021 - present)
Built and scaled a payments API handling 2000 requests per second.

PROJECTS
OrderFlow - an order processing service in FastAPI and PostgreSQL.

EDUCATION
BSc Computer Science, Vassar College
"""


def text_upload(name: str = "resume.txt", body: str = RESUME_TEXT) -> dict:
    return {"file": (name, io.BytesIO(body.encode("utf-8")), "text/plain")}


def blank_pdf(pages: int = 2) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


# -- profile ---------------------------------------------------------------- #


def test_profile_starts_empty_and_can_be_updated(client: TestClient, auth: dict) -> None:
    profile = client.get("/api/v1/profile", headers=auth).json()
    assert profile["skills"] == []

    response = client.put(
        "/api/v1/profile",
        headers=auth,
        json={
            "headline": "Backend engineer",
            "skills": ["Python", "SQL"],
            "years_of_experience": 3.5,
            "preferred_role": "Backend Engineer",
        },
    )
    assert response.status_code == 200
    assert response.json()["skills"] == ["Python", "SQL"]
    assert response.json()["years_of_experience"] == 3.5


def test_an_omitted_field_is_left_alone(client: TestClient, auth: dict) -> None:
    client.put("/api/v1/profile", headers=auth, json={"headline": "Backend engineer"})
    client.put("/api/v1/profile", headers=auth, json={"skills": ["Go"]})

    profile = client.get("/api/v1/profile", headers=auth).json()
    assert profile["headline"] == "Backend engineer"
    assert profile["skills"] == ["Go"]


def test_profile_rejects_an_impossible_experience_value(
    client: TestClient, auth: dict
) -> None:
    response = client.put(
        "/api/v1/profile", headers=auth, json={"years_of_experience": -1}
    )
    assert response.status_code == 422


def test_profiles_are_per_user(client: TestClient) -> None:
    first = register(client, "one@example.com")
    second = register(client, "two@example.com")

    client.put("/api/v1/profile", headers=first, json={"skills": ["Rust"]})
    assert client.get("/api/v1/profile", headers=second).json()["skills"] == []


# -- resume ingestion ------------------------------------------------------- #


def test_resume_upload_extracts_chunks_and_fills_the_profile(
    client: TestClient, auth: dict
) -> None:
    response = client.post("/api/v1/profile/resume", headers=auth, files=text_upload())
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["document"]["doc_type"] == "resume"
    assert body["document"]["chunk_count"] >= 1
    assert body["profile"]["resume_document_id"] == body["document"]["id"]
    # The offline parser reads the SKILLS section.
    assert any("python" in s.lower() for s in body["profile"]["skills"])


def test_parsing_never_overwrites_what_the_candidate_typed(
    client: TestClient, auth: dict
) -> None:
    client.put("/api/v1/profile", headers=auth, json={"headline": "My own headline"})
    body = client.post("/api/v1/profile/resume", headers=auth, files=text_upload()).json()

    assert body["profile"]["headline"] == "My own headline"


def test_an_empty_upload_is_rejected(client: TestClient, auth: dict) -> None:
    files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    assert client.post("/api/v1/profile/resume", headers=auth, files=files).status_code == 400


def test_a_pdf_with_no_extractable_text_is_rejected_with_guidance(
    client: TestClient, auth: dict
) -> None:
    files = {"file": ("scan.pdf", io.BytesIO(blank_pdf()), "application/pdf")}
    response = client.post("/api/v1/profile/resume", headers=auth, files=files)
    assert response.status_code == 422
    assert "OCR" in response.json()["detail"]


def test_a_file_that_is_neither_pdf_nor_text_is_rejected(
    client: TestClient, auth: dict
) -> None:
    files = {"file": ("photo.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")}
    response = client.post("/api/v1/documents/upload", headers=auth, files=files)
    assert response.status_code == 415


def test_documents_can_be_listed_and_deleted(client: TestClient, auth: dict) -> None:
    document = client.post(
        "/api/v1/profile/resume", headers=auth, files=text_upload()
    ).json()["document"]

    assert len(client.get("/api/v1/documents", headers=auth).json()) == 1
    assert client.delete(f"/api/v1/documents/{document['id']}", headers=auth).status_code == 200
    assert client.get("/api/v1/documents", headers=auth).json() == []


def test_one_user_cannot_delete_another_users_document(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    intruder = register(client, "intruder@example.com")

    document = client.post(
        "/api/v1/profile/resume", headers=owner, files=text_upload()
    ).json()["document"]

    assert client.delete(f"/api/v1/documents/{document['id']}", headers=intruder).status_code == 404
    assert len(client.get("/api/v1/documents", headers=owner).json()) == 1


def test_document_search_only_returns_the_callers_own_chunks(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    other = register(client, "other@example.com")
    client.post("/api/v1/profile/resume", headers=owner, files=text_upload())

    assert client.get("/api/v1/documents/search?q=python", headers=owner).json()["results"]
    assert client.get("/api/v1/documents/search?q=python", headers=other).json()["results"] == []


# -- job descriptions ------------------------------------------------------- #


def test_a_job_description_can_be_pasted(client: TestClient, auth: dict) -> None:
    response = client.post(
        "/api/v1/jobs", headers=auth, json={"raw_text": SAMPLE_JOB}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["is_active"] is True
    # The offline parser recovers a title from the text when none was given.
    assert body["title"]


def test_a_too_short_job_description_is_rejected(client: TestClient, auth: dict) -> None:
    response = client.post("/api/v1/jobs", headers=auth, json={"raw_text": "hiring"})
    assert response.status_code == 422


def test_only_one_job_description_is_active_at_a_time(
    client: TestClient, auth: dict
) -> None:
    first = client.post(
        "/api/v1/jobs", headers=auth, json={"title": "One", "raw_text": SAMPLE_JOB}
    ).json()
    second = client.post(
        "/api/v1/jobs", headers=auth, json={"title": "Two", "raw_text": SAMPLE_JOB}
    ).json()

    jobs = {j["id"]: j for j in client.get("/api/v1/jobs", headers=auth).json()}
    assert jobs[first["id"]]["is_active"] is False
    assert jobs[second["id"]]["is_active"] is True

    client.post(f"/api/v1/jobs/{first['id']}/activate", headers=auth)
    jobs = {j["id"]: j for j in client.get("/api/v1/jobs", headers=auth).json()}
    assert jobs[first["id"]]["is_active"] is True
    assert jobs[second["id"]]["is_active"] is False


def test_a_job_description_can_be_uploaded_as_a_file(
    client: TestClient, auth: dict
) -> None:
    files = {"file": ("jd.txt", io.BytesIO(SAMPLE_JOB.encode()), "text/plain")}
    response = client.post(
        "/api/v1/jobs/upload", headers=auth, files=files, data={"title": "Backend Engineer"}
    )
    assert response.status_code == 201
    assert response.json()["source_document_id"]


def test_job_descriptions_are_private_to_their_owner(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    intruder = register(client, "intruder@example.com")
    job = client.post("/api/v1/jobs", headers=owner, json={"raw_text": SAMPLE_JOB}).json()

    assert client.get(f"/api/v1/jobs/{job['id']}", headers=intruder).status_code == 404
    assert client.get("/api/v1/jobs", headers=intruder).json() == []


# -- text utilities --------------------------------------------------------- #


def test_clean_text_rejoins_words_split_across_lines() -> None:
    assert "engineering" in clean_text("engine-\nering")


def test_clean_text_collapses_blank_runs_but_keeps_structure() -> None:
    cleaned = clean_text("Heading\n\n\n\nBody   text")
    assert cleaned == "Heading\n\nBody text"


def test_short_text_is_a_single_chunk() -> None:
    assert chunk_text("short", 100, 20) == ["short"]


def test_empty_text_produces_no_chunks() -> None:
    assert chunk_text("   ", 100, 20) == []


def test_chunks_overlap_so_a_boundary_fact_stays_retrievable() -> None:
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_text(text, 200, 50)

    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)

    # Consecutive chunks must genuinely share text, or a sentence straddling the
    # boundary would be retrievable from neither side.
    for current, following in zip(chunks, chunks[1:]):
        shared = max(
            (
                size
                for size in range(1, min(len(current), len(following)) + 1)
                if following.startswith(current[-size:])
            ),
            default=0,
        )
        assert shared >= 20, f"only {shared} characters of overlap"


def test_every_word_survives_chunking() -> None:
    text = " ".join(f"word{i}" for i in range(500))
    joined = " ".join(chunk_text(text, 200, 50))

    assert all(f"word{i}" in joined for i in range(500))


def test_chunking_rejects_an_overlap_it_could_not_honour() -> None:
    with pytest.raises(ValueError):
        chunk_text("some text here", 100, 100)


def test_offsets_map_back_to_the_right_page() -> None:
    # Two pages of 10 characters each, joined with a 2-character separator.
    assert page_for_offset([12, 12], 0) == 1
    assert page_for_offset([12, 12], 11) == 1
    assert page_for_offset([12, 12], 12) == 2
    # Past the end, clamp to the last page rather than raising.
    assert page_for_offset([12, 12], 999) == 2

"""Dashboard aggregation, health, and the administrator views."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import register
from tests.test_interviews import STRONG_ANSWER, play_through


def make_admin(email: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        user.role = UserRole.ADMIN.value
        db.commit()


def test_a_new_user_gets_an_empty_but_valid_dashboard(
    client: TestClient, auth: dict
) -> None:
    body = client.get("/api/v1/dashboard", headers=auth).json()

    assert body["total_interviews"] == 0
    assert body["average_score"] is None
    assert body["rubric_averages"] is None
    assert body["weak_topics"] == []
    assert body["progress"] == []
    assert body["latest_plan"] is None


def test_a_completed_interview_populates_every_panel(
    client: TestClient, ready_candidate: dict
) -> None:
    interview_id = play_through(client, ready_candidate)
    client.post(f"/api/v1/interviews/{interview_id}/complete", headers=ready_candidate)

    body = client.get("/api/v1/dashboard", headers=ready_candidate).json()

    assert body["total_interviews"] == 1
    assert body["completed_interviews"] == 1
    assert body["total_answers"] >= 1
    assert 0 <= body["average_score"] <= 10
    assert body["best_score"] is not None

    rubric = body["rubric_averages"]
    assert set(rubric) == {
        "correctness",
        "relevance",
        "clarity",
        "completeness",
        "communication",
    }
    assert all(0 <= value <= 10 for value in rubric.values())

    assert body["strongest_topics"], "topic performance should be reported"
    assert len(body["progress"]) == 1
    assert body["latest_plan"] is not None
    assert body["recent_interviews"][0]["id"] == interview_id


def test_an_in_progress_interview_counts_but_does_not_appear_as_progress(
    client: TestClient, ready_candidate: dict
) -> None:
    started = client.post(
        "/api/v1/interviews", headers=ready_candidate, json={"question_count": 4}
    ).json()
    client.post(
        f"/api/v1/interviews/{started['interview']['id']}/answer",
        headers=ready_candidate,
        json={"question_id": started["first_question"]["id"], "answer_text": STRONG_ANSWER},
    )

    body = client.get("/api/v1/dashboard", headers=ready_candidate).json()
    assert body["total_interviews"] == 1
    assert body["completed_interviews"] == 0
    assert body["total_answers"] >= 1
    # The progress chart plots finished interviews only.
    assert body["progress"] == []


def test_weak_topics_are_the_ones_below_the_threshold(
    client: TestClient, ready_candidate: dict
) -> None:
    interview_id = play_through(client, ready_candidate, text="I don't know.")
    client.post(f"/api/v1/interviews/{interview_id}/complete", headers=ready_candidate)

    body = client.get("/api/v1/dashboard", headers=ready_candidate).json()
    assert body["weak_topics"], "poor answers should surface weak topics"
    assert all(topic["average_score"] < 6.5 for topic in body["weak_topics"])
    assert all(topic["answer_count"] >= 1 for topic in body["weak_topics"])


def test_one_users_results_never_leak_into_anothers_dashboard(
    client: TestClient,
) -> None:
    owner = register(client, "owner@example.com")
    other = register(client, "other@example.com")

    interview_id = play_through(client, owner)
    client.post(f"/api/v1/interviews/{interview_id}/complete", headers=owner)

    assert client.get("/api/v1/dashboard", headers=other).json()["total_interviews"] == 0
    assert client.get("/api/v1/dashboard", headers=owner).json()["total_interviews"] == 1


# -- health and admin -------------------------------------------------------- #


def test_health_reports_the_resolved_backends(client: TestClient) -> None:
    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["database_ok"] is True
    assert body["llm_provider"] == "offline"
    assert body["embedding_provider"] == "hashing"
    assert body["vector_backend"] == "fallback"


def test_the_root_route_points_at_the_docs(client: TestClient) -> None:
    body = client.get("/").json()
    assert body["docs"] == "/docs"


def test_admin_overview_counts_across_all_users(client: TestClient) -> None:
    admin = register(client, "admin@example.com")
    candidate = register(client, "candidate@example.com")
    make_admin("admin@example.com")

    interview_id = play_through(client, candidate)
    client.post(f"/api/v1/interviews/{interview_id}/complete", headers=candidate)

    body = client.get("/api/v1/admin/overview", headers=admin).json()
    assert body["total_users"] == 2
    assert body["total_interviews"] == 1
    assert body["completed_interviews"] == 1
    assert body["average_score"] is not None


def test_admin_can_list_users(client: TestClient) -> None:
    admin = register(client, "admin@example.com")
    register(client, "candidate@example.com")
    make_admin("admin@example.com")

    users = client.get("/api/v1/admin/users", headers=admin).json()
    assert {u["email"] for u in users} == {"admin@example.com", "candidate@example.com"}
    # Password hashes must never appear in a response.
    assert all("password" not in key for user in users for key in user)

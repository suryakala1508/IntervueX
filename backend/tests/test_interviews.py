"""The interview lifecycle: start, adaptive turns, evaluation, completion."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.models.enums import Difficulty
from tests.conftest import SAMPLE_JOB, register

STRONG_ANSWER = (
    "I would expose the endpoint with FastAPI and keep the write path in a single "
    "PostgreSQL transaction so partial orders can never be persisted. For "
    "performance I add a composite index on (customer_id, created_at) because that "
    "is the access pattern the listing screen uses, and I measure with EXPLAIN "
    "ANALYZE before and after rather than guessing. Connection pooling is handled "
    "by SQLAlchemy's pool with pool_pre_ping so recycled connections do not surface "
    "as request errors. For correctness I write pytest cases covering the empty "
    "result, the duplicate submission, and the concurrent update, and I load test "
    "with a realistic row count because an index that helps at a thousand rows can "
    "be ignored by the planner at ten million."
)

WEAK_ANSWER = "I don't really know."


def start_interview(client: TestClient, auth: dict, **overrides) -> dict:
    payload = {"question_count": 4, **overrides}
    response = client.post("/api/v1/interviews", headers=auth, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def answer(client: TestClient, auth: dict, interview_id: str, question_id: str, text: str) -> dict:
    response = client.post(
        f"/api/v1/interviews/{interview_id}/answer",
        headers=auth,
        json={"question_id": question_id, "answer_text": text},
    )
    assert response.status_code == 200, response.text
    return response.json()


def play_through(client: TestClient, auth: dict, text: str = STRONG_ANSWER) -> str:
    """Run an interview to completion; returns the interview id."""
    started = start_interview(client, auth)
    interview_id = started["interview"]["id"]
    question = started["first_question"]

    for _ in range(25):  # generous bound; the workflow decides when to stop
        turn = answer(client, auth, interview_id, question["id"], text)
        if turn["finished"] or not turn["next_question"]:
            break
        question = turn["next_question"]
    return interview_id


# -- starting --------------------------------------------------------------- #


def test_starting_an_interview_returns_a_grounded_first_question(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate)

    assert started["interview"]["status"] == "in_progress"
    question = started["first_question"]
    assert question["position"] == 1
    assert question["question_text"].strip()
    assert question["category"] in {"technical", "project", "behavioral", "role_specific"}
    assert started["workflow_events"], "the workflow should report the steps it ran"


def test_an_interview_works_without_a_profile_or_job(
    client: TestClient, auth: dict
) -> None:
    # A brand-new user must still be able to practise; the workflow falls back to
    # generic role context rather than failing.
    started = start_interview(client, auth)
    assert started["first_question"]["question_text"].strip()


def test_the_requested_difficulty_is_respected(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate, starting_difficulty="hard")
    assert started["interview"]["current_difficulty"] == "hard"


def test_question_count_is_bounded(client: TestClient, auth: dict) -> None:
    assert client.post("/api/v1/interviews", headers=auth, json={"question_count": 1}).status_code == 422
    assert client.post("/api/v1/interviews", headers=auth, json={"question_count": 99}).status_code == 422


def test_starting_against_someone_elses_job_is_refused(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    intruder = register(client, "intruder@example.com")
    job = client.post("/api/v1/jobs", headers=owner, json={"raw_text": SAMPLE_JOB}).json()

    response = client.post(
        "/api/v1/interviews", headers=intruder, json={"job_description_id": job["id"]}
    )
    assert response.status_code == 404


# -- answering -------------------------------------------------------------- #


def test_an_answer_is_graded_against_the_full_rubric(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate)
    turn = answer(
        client,
        ready_candidate,
        started["interview"]["id"],
        started["first_question"]["id"],
        STRONG_ANSWER,
    )

    evaluation = turn["evaluation"]
    for field in (
        "score",
        "correctness",
        "relevance",
        "clarity",
        "completeness",
        "communication",
    ):
        assert 0 <= evaluation[field] <= 10, field
    assert evaluation["quality"] in {"strong", "adequate", "weak", "incomplete"}
    assert isinstance(evaluation["strengths"], list)
    assert isinstance(evaluation["suggestions"], list)
    assert turn["progress"]


def test_a_substantive_answer_outscores_an_empty_one(
    client: TestClient, ready_candidate: dict
) -> None:
    first = start_interview(client, ready_candidate)
    strong = answer(
        client, ready_candidate, first["interview"]["id"], first["first_question"]["id"], STRONG_ANSWER
    )

    second = start_interview(client, ready_candidate)
    weak = answer(
        client, ready_candidate, second["interview"]["id"], second["first_question"]["id"], WEAK_ANSWER
    )

    assert strong["evaluation"]["score"] > weak["evaluation"]["score"]


def test_the_interview_adapts_downward_after_a_weak_answer(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate, starting_difficulty="hard")
    turn = answer(
        client, ready_candidate, started["interview"]["id"], started["first_question"]["id"], WEAK_ANSWER
    )

    assert turn["evaluation"]["quality"] in {"weak", "incomplete"}
    assert turn["next_question"] is not None
    # A struggling candidate must not be handed something harder.
    assert (
        Difficulty(turn["next_question"]["difficulty"]).rank
        <= Difficulty(started["first_question"]["difficulty"]).rank
    )


def test_a_question_cannot_be_answered_twice(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate)
    interview_id = started["interview"]["id"]
    question_id = started["first_question"]["id"]
    answer(client, ready_candidate, interview_id, question_id, STRONG_ANSWER)

    response = client.post(
        f"/api/v1/interviews/{interview_id}/answer",
        headers=ready_candidate,
        json={"question_id": question_id, "answer_text": "second attempt"},
    )
    assert response.status_code == 409


def test_a_question_from_another_interview_is_refused(
    client: TestClient, ready_candidate: dict
) -> None:
    first = start_interview(client, ready_candidate)
    second = start_interview(client, ready_candidate)

    response = client.post(
        f"/api/v1/interviews/{first['interview']['id']}/answer",
        headers=ready_candidate,
        json={
            "question_id": second["first_question"]["id"],
            "answer_text": STRONG_ANSWER,
        },
    )
    assert response.status_code == 404


def test_an_empty_answer_is_rejected(client: TestClient, ready_candidate: dict) -> None:
    started = start_interview(client, ready_candidate)
    response = client.post(
        f"/api/v1/interviews/{started['interview']['id']}/answer",
        headers=ready_candidate,
        json={"question_id": started["first_question"]["id"], "answer_text": ""},
    )
    assert response.status_code == 422


def test_one_user_cannot_answer_anothers_interview(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    intruder = register(client, "intruder@example.com")
    started = start_interview(client, owner)

    response = client.post(
        f"/api/v1/interviews/{started['interview']['id']}/answer",
        headers=intruder,
        json={
            "question_id": started["first_question"]["id"],
            "answer_text": STRONG_ANSWER,
        },
    )
    assert response.status_code == 404


# -- streaming -------------------------------------------------------------- #


def test_the_streaming_turn_emits_steps_then_a_result(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate)
    with client.stream(
        "POST",
        f"/api/v1/interviews/{started['interview']['id']}/answer/stream",
        headers=ready_candidate,
        json={
            "question_id": started["first_question"]["id"],
            "answer_text": STRONG_ANSWER,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    events = [line[len("event: ") :] for line in body.splitlines() if line.startswith("event: ")]
    assert "step" in events
    assert events[-2:] == ["result", "done"]

    payload = next(
        json.loads(line[len("data: ") :])
        for previous, line in zip(body.splitlines(), body.splitlines()[1:])
        if previous == "event: result"
    )
    assert payload["evaluation"]["score"] >= 0


def test_streaming_reports_an_invalid_request_as_an_http_error(
    client: TestClient, ready_candidate: dict
) -> None:
    # Validation happens before the stream opens, so the client gets a real
    # status code rather than an error buried inside a 200 response.
    started = start_interview(client, ready_candidate)
    response = client.post(
        f"/api/v1/interviews/{started['interview']['id']}/answer/stream",
        headers=ready_candidate,
        json={"question_id": "does-not-exist", "answer_text": STRONG_ANSWER},
    )
    assert response.status_code == 404


# -- completing ------------------------------------------------------------- #


def test_completing_an_interview_scores_it_and_builds_a_plan(
    client: TestClient, ready_candidate: dict
) -> None:
    interview_id = play_through(client, ready_candidate)

    response = client.post(f"/api/v1/interviews/{interview_id}/complete", headers=ready_candidate)
    assert response.status_code == 200
    body = response.json()

    assert body["interview"]["status"] == "completed"
    assert body["interview"]["overall_score"] is not None
    plan = body["improvement_plan"]
    assert plan["daily_plan"], "a plan should contain day-by-day practice"
    assert plan["overview"]


def test_an_unanswered_interview_cannot_be_completed(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate)
    response = client.post(
        f"/api/v1/interviews/{started['interview']['id']}/complete", headers=ready_candidate
    )
    assert response.status_code == 409


def test_a_completed_interview_stops_accepting_answers(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate)
    interview_id = started["interview"]["id"]
    turn = answer(
        client, ready_candidate, interview_id, started["first_question"]["id"], STRONG_ANSWER
    )
    client.post(f"/api/v1/interviews/{interview_id}/complete", headers=ready_candidate)

    next_question = turn["next_question"]
    if next_question:
        response = client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            headers=ready_candidate,
            json={"question_id": next_question["id"], "answer_text": STRONG_ANSWER},
        )
        assert response.status_code == 409


def test_the_plan_is_only_available_once_the_interview_is_complete(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate)
    interview_id = started["interview"]["id"]
    assert client.get(f"/api/v1/interviews/{interview_id}/plan", headers=ready_candidate).status_code == 404

    answer(client, ready_candidate, interview_id, started["first_question"]["id"], STRONG_ANSWER)
    client.post(f"/api/v1/interviews/{interview_id}/complete", headers=ready_candidate)

    assert client.get(f"/api/v1/interviews/{interview_id}/plan", headers=ready_candidate).status_code == 200


def test_an_interview_can_be_abandoned(client: TestClient, ready_candidate: dict) -> None:
    started = start_interview(client, ready_candidate)
    response = client.post(
        f"/api/v1/interviews/{started['interview']['id']}/abandon", headers=ready_candidate
    )
    assert response.json()["status"] == "abandoned"


# -- history ---------------------------------------------------------------- #


def test_the_transcript_records_every_question_and_answer(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate)
    interview_id = started["interview"]["id"]
    answer(client, ready_candidate, interview_id, started["first_question"]["id"], STRONG_ANSWER)

    detail = client.get(f"/api/v1/interviews/{interview_id}", headers=ready_candidate).json()
    assert len(detail["turns"]) >= 1

    first_turn = detail["turns"][0]
    assert first_turn["question"]["id"] == started["first_question"]["id"]
    assert first_turn["answer"]["answer_text"] == STRONG_ANSWER
    assert first_turn["answer"]["evaluation"]["score"] >= 0
    assert detail["current_question"] is not None


def test_interviews_are_listed_newest_first_and_are_private(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    intruder = register(client, "intruder@example.com")
    start_interview(client, owner)
    start_interview(client, owner)

    assert len(client.get("/api/v1/interviews", headers=owner).json()) == 2
    assert client.get("/api/v1/interviews", headers=intruder).json() == []


def test_an_interview_can_be_deleted_with_its_history(
    client: TestClient, ready_candidate: dict
) -> None:
    started = start_interview(client, ready_candidate)
    interview_id = started["interview"]["id"]
    answer(client, ready_candidate, interview_id, started["first_question"]["id"], STRONG_ANSWER)

    assert client.delete(f"/api/v1/interviews/{interview_id}", headers=ready_candidate).status_code == 200
    assert client.get(f"/api/v1/interviews/{interview_id}", headers=ready_candidate).status_code == 404


def test_reading_someone_elses_interview_is_a_404(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    intruder = register(client, "intruder@example.com")
    started = start_interview(client, owner)

    assert client.get(
        f"/api/v1/interviews/{started['interview']['id']}", headers=intruder
    ).status_code == 404


# -- the AI tool audit trail ------------------------------------------------- #


def test_every_ai_step_is_recorded_in_the_tool_log(client: TestClient) -> None:
    admin_headers = register(client, "admin@example.com")
    candidate = register(client, "candidate@example.com")
    start_interview(client, candidate)

    # Promote the first user so the audit trail can be inspected.
    from app.db.session import SessionLocal
    from app.models.enums import UserRole
    from app.models.user import User

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "admin@example.com").one()
        user.role = UserRole.ADMIN.value
        db.commit()

    logs = client.get("/api/v1/admin/tool-logs", headers=admin_headers).json()
    names = {log["tool_name"] for log in logs}

    assert "get_candidate_profile" in names
    assert "generate_interview_question" in names or "save_interview_question" in names
    assert all(log["duration_ms"] >= 0 for log in logs)

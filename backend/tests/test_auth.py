"""Registration, login, tokens, and route protection."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import (
    create_refresh_token,
    hash_password,
    verify_password,
)

CREDENTIALS = {
    "email": "ada@example.com",
    "full_name": "Ada Lovelace",
    "password": "password123",
}


def test_register_returns_tokens_and_creates_a_profile(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=CREDENTIALS)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    me = client.get("/api/v1/users/me", headers=headers).json()
    assert me["email"] == "ada@example.com"
    assert me["role"] == "candidate"

    # Registration seeds an empty profile so the UI has something to edit.
    assert client.get("/api/v1/profile", headers=headers).status_code == 200


def test_email_is_normalised_and_must_be_unique(client: TestClient) -> None:
    assert client.post("/api/v1/auth/register", json=CREDENTIALS).status_code == 201

    duplicate = {**CREDENTIALS, "email": "ADA@Example.com "}
    response = client.post("/api/v1/auth/register", json=duplicate)
    assert response.status_code == 409

    # ...and the normalised address is what logs in.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ADA@EXAMPLE.COM", "password": CREDENTIALS["password"]},
    )
    assert login.status_code == 200


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"email": "not-an-email", "full_name": "X", "password": "password123"}, "email"),
        ({"email": "a@b.com", "full_name": "X", "password": "short"}, "password length"),
        ({"email": "a@b.com", "full_name": "   ", "password": "password123"}, "blank name"),
    ],
)
def test_registration_rejects_invalid_input(
    client: TestClient, payload: dict, reason: str
) -> None:
    assert client.post("/api/v1/auth/register", json=payload).status_code == 422, reason


def test_login_rejects_a_wrong_password(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=CREDENTIALS)
    response = client.post(
        "/api/v1/auth/login", json={"email": CREDENTIALS["email"], "password": "wrong"}
    )
    assert response.status_code == 401
    # The message must not reveal whether the account exists.
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_for_an_unknown_account_gives_the_same_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_refresh_exchanges_a_refresh_token_for_a_new_pair(client: TestClient) -> None:
    tokens = client.post("/api/v1/auth/register", json=CREDENTIALS).json()
    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_an_access_token_is_not_accepted_as_a_refresh_token(client: TestClient) -> None:
    tokens = client.post("/api/v1/auth/register", json=CREDENTIALS).json()
    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert response.status_code == 401


def test_a_refresh_token_is_not_accepted_as_an_access_token(client: TestClient) -> None:
    tokens = client.post("/api/v1/auth/register", json=CREDENTIALS).json()
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert response.status_code == 401


def test_a_token_for_a_deleted_user_is_rejected(client: TestClient) -> None:
    # A validly signed token whose subject does not exist must not authenticate.
    token = create_refresh_token("00000000-0000-0000-0000-000000000000")
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path", ["/api/v1/users/me", "/api/v1/profile", "/api/v1/dashboard", "/api/v1/interviews"]
)
def test_protected_routes_require_a_token(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401


def test_a_garbage_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert response.status_code == 401


def test_admin_routes_are_closed_to_candidates(client: TestClient, auth: dict) -> None:
    assert client.get("/api/v1/admin/overview", headers=auth).status_code == 403
    assert client.get("/api/v1/admin/users", headers=auth).status_code == 403


def test_password_hashing_round_trip() -> None:
    digest = hash_password("correct horse battery staple")
    assert digest != "correct horse battery staple"
    assert verify_password("correct horse battery staple", digest)
    assert not verify_password("wrong password", digest)


def test_hashing_rejects_a_password_bcrypt_would_truncate() -> None:
    # bcrypt silently ignores anything past 72 bytes; accepting it would mean
    # two different passwords opening the same account.
    with pytest.raises(ValueError):
        hash_password("a" * 73)


def test_verify_survives_a_malformed_stored_hash() -> None:
    assert not verify_password("anything", "not-a-bcrypt-hash")

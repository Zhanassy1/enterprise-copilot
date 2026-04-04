"""Auth invite_token body validation (no database)."""

from fastapi.testclient import TestClient


def test_auth_login_short_invite_token_422(client: TestClient) -> None:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "x@example.com", "password": "password", "invite_token": "short"},
    )
    assert r.status_code == 422


def test_auth_register_short_invite_token_422(client: TestClient) -> None:
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "x@example.com",
            "password": "password1",
            "full_name": None,
            "invite_token": "short",
        },
    )
    assert r.status_code == 422

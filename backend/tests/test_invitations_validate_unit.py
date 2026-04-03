"""Invitation validate — query validation (no database)."""

from fastapi.testclient import TestClient


def test_invitations_validate_short_token_422(client: TestClient) -> None:
    r = client.get("/api/v1/invitations/validate?token=short")
    assert r.status_code == 422

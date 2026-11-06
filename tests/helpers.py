"""Test helpers: small builders over the public HTTP API."""

from fastapi.testclient import TestClient

API = "/api/v1"


def auth(token: str) -> dict[str, str]:
    """Return the Authorization header for ``token``."""
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, email: str, display_name: str = "Someone") -> tuple[dict, str]:
    """Register a user and return ``(user, token)``."""
    response = client.post(f"{API}/users", json={"email": email, "display_name": display_name})
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    return data["user"], data["token"]


def create_team(client: TestClient, token: str, name: str = "Team") -> dict:
    """Create a team as the bearer of ``token`` and return it."""
    response = client.post(f"{API}/teams", json={"name": name}, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def add_member(client: TestClient, token: str, team_id: int, email: str, role: str = "member"):
    """Add ``email`` to the team and return the response."""
    return client.post(
        f"{API}/teams/{team_id}/members", json={"email": email, "role": role}, headers=auth(token)
    )


def create_note(client: TestClient, token: str, team_id: int, **fields) -> dict:
    """Create a note in the team and return it."""
    payload = {"title": "A note", "body": "", "tags": []} | fields
    response = client.post(f"{API}/teams/{team_id}/notes", json=payload, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()["data"]

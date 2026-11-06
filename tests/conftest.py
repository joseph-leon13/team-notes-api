"""Shared fixtures and factories.

Every test gets a fresh app backed by its own temporary SQLite file. A temp *file* (not
``:memory:``) is used on purpose: SQLite's in-memory databases are per-connection, and
FastAPI's TestClient may serve requests from other threads, which would then see an
empty database.

The factories below drive the public HTTP API, so tests read as behaviour rather than
setup. Test modules import them with ``from conftest import ...`` (pytest puts this
directory on ``sys.path``, since ``tests/`` has no ``__init__.py``).
"""

import pytest
from fastapi.testclient import TestClient

from team_notes_api.core.config import Settings
from team_notes_api.main import create_app

API = "/api/v1"


@pytest.fixture
def client(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def auth(token: str) -> dict[str, str]:
    """Return the Authorization header for ``token``."""
    return {"Authorization": f"Bearer {token}"}


def make_user(client: TestClient, email: str, display_name: str = "Someone") -> tuple[dict, str]:
    """Register a user and return ``(user, token)``."""
    response = client.post(f"{API}/users", json={"email": email, "display_name": display_name})
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    return data["user"], data["token"]


def make_team(client: TestClient, token: str, name: str = "Team") -> dict:
    """Create a team as the bearer of ``token`` and return it."""
    response = client.post(f"{API}/teams", json={"name": name}, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def add_member(client: TestClient, token: str, team_id: int, email: str, role: str = "member"):
    """Ask to add ``email`` to the team as the bearer of ``token``; return the response."""
    return client.post(
        f"{API}/teams/{team_id}/members", json={"email": email, "role": role}, headers=auth(token)
    )


def make_note(client: TestClient, token: str, team_id: int, **fields) -> dict:
    """Create a note in the team and return it. ``fields`` override title/body/tags."""
    payload = {"title": "A note", "body": "", "tags": []} | fields
    response = client.post(f"{API}/teams/{team_id}/notes", json=payload, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()["data"]

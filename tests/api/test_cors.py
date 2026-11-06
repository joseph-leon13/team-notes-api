"""CORS: off by default, explicit allow-list when configured."""

from fastapi.testclient import TestClient

from team_notes_api.core.config import Settings
from team_notes_api.main import create_app

ORIGIN = "https://notes.example.com"
PREFLIGHT = {"Origin": ORIGIN, "Access-Control-Request-Method": "GET"}


def test_no_cors_headers_by_default(client):
    response = client.options("/api/v1/users/me", headers=PREFLIGHT)

    assert "access-control-allow-origin" not in response.headers


def test_configured_origin_is_allowed(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cors.db'}", cors_origins=ORIGIN)
    with TestClient(create_app(settings)) as client:
        response = client.options("/api/v1/users/me", headers=PREFLIGHT)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_unlisted_origin_is_not_allowed(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cors.db'}", cors_origins=ORIGIN)
    with TestClient(create_app(settings)) as client:
        response = client.options(
            "/api/v1/users/me",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        )

    assert "access-control-allow-origin" not in response.headers

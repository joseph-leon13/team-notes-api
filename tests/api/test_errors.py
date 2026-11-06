"""Every error leaves the service in the ``{"error": {code, message, details}}`` envelope."""

from fastapi.testclient import TestClient

from team_notes_api.core.config import Settings
from team_notes_api.main import create_app


def assert_error_envelope(response, status: int, code: str) -> dict:
    """Assert ``response`` is an enveloped error with the given status and code."""
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    assert isinstance(body["error"]["details"], dict)
    return body["error"]


def test_unknown_route_returns_enveloped_404(client):
    response = client.get("/definitely/not/a/route")

    assert_error_envelope(response, 404, "not_found")


def test_wrong_method_returns_enveloped_405_with_allow_header(client):
    response = client.delete("/health")

    assert_error_envelope(response, 405, "method_not_allowed")
    assert "GET" in response.headers["allow"]


def test_unexpected_exception_returns_500_without_leaking_details(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}"))

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    error = assert_error_envelope(response, 500, "internal_error")
    assert "secret" not in response.text
    assert error["details"] == {}

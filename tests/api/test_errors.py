"""Every error leaves the service in the ``{"error": {code, message, details}}`` envelope."""

from conftest import API, add_member, auth, make_note, make_team, make_user
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


def test_every_error_status_uses_the_envelope(client):
    _, owner = make_user(client, "owner@example.com")
    _, member = make_user(client, "member@example.com")
    team = make_team(client, owner)
    add_member(client, owner, team["id"], "member@example.com")
    note = make_note(client, owner, team["id"])

    cases = [
        (client.get(f"{API}/users/me"), 401, "unauthenticated"),
        (client.delete(f"{API}/notes/{note['id']}", headers=auth(member)), 403, "forbidden"),
        (client.get(f"{API}/notes/999", headers=auth(owner)), 404, "not_found"),
        (client.put(f"{API}/notes/{note['id']}", headers=auth(owner)), 405, "method_not_allowed"),
        (add_member(client, owner, team["id"], "member@example.com"), 409, "conflict"),
        (
            client.patch(f"{API}/notes/{note['id']}", json={"version": 1}, headers=auth(owner)),
            422,
            "validation_error",
        ),
    ]

    for response, status, code in cases:
        assert_error_envelope(response, status, code)


def test_validation_errors_list_location_and_reason_without_echoing_input(client):
    response = client.post(
        "/api/v1/users", json={"email": "x@y.co", "display_name": "", "secret": "hunter2"}
    )

    error = assert_error_envelope(response, 422, "validation_error")
    locations = {tuple(item["loc"]) for item in error["details"]["errors"]}
    assert ("body", "display_name") in locations
    assert ("body", "secret") in locations
    assert all(set(item) == {"loc", "msg", "type"} for item in error["details"]["errors"])
    assert "hunter2" not in response.text


def test_malformed_json_body_is_422_envelope(client):
    response = client.post(
        "/api/v1/users", content=b"{not json", headers={"Content-Type": "application/json"}
    )

    assert_error_envelope(response, 422, "validation_error")


def test_non_integer_path_id_is_422(client):
    _, token = make_user(client, "a@example.com")

    response = client.get(f"{API}/notes/abc", headers=auth(token))

    assert_error_envelope(response, 422, "validation_error")


def test_openapi_documents_summary_and_error_codes_for_every_operation(client):
    spec = client.get("/openapi.json").json()

    for path, operations in spec["paths"].items():
        if not path.startswith("/api/v1"):
            continue
        for method, operation in operations.items():
            assert operation.get("summary"), f"{method.upper()} {path} has no summary"
            assert operation.get("description"), f"{method.upper()} {path} has no description"
            label = f"{method.upper()} {path}"
            if (method, path) != ("post", "/api/v1/users"):
                assert "401" in operation["responses"], f"{label} does not document 401"
            for status, response in operation["responses"].items():
                if status.startswith("4"):
                    schema = response["content"]["application/json"]["schema"]
                    assert schema == {"$ref": "#/components/schemas/ErrorEnvelope"}, (
                        f"{label} documents {status} with a non-envelope schema"
                    )
    assert "HTTPBearer" in spec["components"]["securitySchemes"]

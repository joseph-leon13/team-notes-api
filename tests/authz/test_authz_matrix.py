"""Authorization matrix over every ``/api/v1`` route, plus a route-coverage gate.

Each (route, actor) pair runs against a fresh database and asserts the exact status.
The gate walks ``app.routes`` and fails if any route is in neither the matrix nor the
explicit PUBLIC set, so a future endpoint cannot ship without an authorization decision.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import API, add_member, auth, make_note, make_team, make_user
from fastapi.routing import APIRoute, iter_route_contexts

import team_notes_api

ACTORS = ("no_token", "bad_token", "non_member", "member", "owner")


@dataclass(frozen=True)
class World:
    """A team (owner + member), an outsider, a note by the owner, and a spare user."""

    tokens: dict[str, str | None]
    team_id: int
    note_id: int
    member_id: int
    spare_email: str


def build_world(client) -> World:
    """Create the fixed cast every matrix case runs against."""
    _, owner_token = make_user(client, "owner@example.com")
    member, member_token = make_user(client, "member@example.com")
    _, outsider_token = make_user(client, "outsider@example.com")
    make_user(client, "spare@example.com")
    team = make_team(client, owner_token)
    assert add_member(client, owner_token, team["id"], "member@example.com").status_code == 201
    note = make_note(client, owner_token, team["id"])
    return World(
        tokens={
            "no_token": None,
            "bad_token": "definitely-not-a-token",
            "non_member": outsider_token,
            "member": member_token,
            "owner": owner_token,
        },
        team_id=team["id"],
        note_id=note["id"],
        member_id=member["id"],
        spare_email="spare@example.com",
    )


def _request_for(method: str, path: str, world: World) -> tuple[str, dict | None]:
    """Return the concrete URL and JSON body exercising ``(method, path)``."""
    url = API + path.format(team_id=world.team_id, note_id=world.note_id, user_id=world.member_id)
    bodies = {
        ("POST", "/teams"): {"name": "New team"},
        ("POST", "/teams/{team_id}/members"): {"email": world.spare_email},
        ("POST", "/teams/{team_id}/notes"): {"title": "Hello"},
        ("PATCH", "/notes/{note_id}"): {"version": 1, "title": "Edited"},
    }
    return url, bodies.get((method, path))


# (method, path under /api/v1) -> expected status per actor, in ACTORS order.
# The DELETE-member case targets the plain member: for the member it is a self-leave.
# The DELETE-note case targets a note created by the owner.
MATRIX: dict[tuple[str, str], tuple[int, int, int, int, int]] = {
    ("GET", "/users/me"): (401, 401, 200, 200, 200),
    ("POST", "/teams"): (401, 401, 201, 201, 201),
    ("GET", "/teams"): (401, 401, 200, 200, 200),
    ("GET", "/teams/{team_id}"): (401, 401, 404, 200, 200),
    ("POST", "/teams/{team_id}/members"): (401, 401, 404, 403, 201),
    ("DELETE", "/teams/{team_id}/members/{user_id}"): (401, 401, 404, 204, 204),
    ("POST", "/teams/{team_id}/notes"): (401, 401, 404, 201, 201),
    ("GET", "/teams/{team_id}/notes"): (401, 401, 404, 200, 200),
    ("GET", "/notes/{note_id}"): (401, 401, 404, 200, 200),
    ("PATCH", "/notes/{note_id}"): (401, 401, 404, 200, 200),
    ("DELETE", "/notes/{note_id}"): (401, 401, 404, 403, 204),
}

PUBLIC: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("POST", f"{API}/users"),
    ("GET", "/openapi.json"),
    ("GET", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/redoc"),
}

CASES = [
    pytest.param(method, path, actor, expected[i], id=f"{method} {path} as {actor}")
    for (method, path), expected in MATRIX.items()
    for i, actor in enumerate(ACTORS)
]


@pytest.mark.parametrize(("method", "path", "actor", "expected"), CASES)
def test_authorization_matrix(client, method, path, actor, expected):
    world = build_world(client)
    url, body = _request_for(method, path, world)
    token = world.tokens[actor]
    headers = auth(token) if token else {}

    response = client.request(method, url, json=body, headers=headers)

    assert response.status_code == expected, response.text
    if expected >= 400:
        assert (
            response.json()["error"]["code"]
            == {
                401: "unauthenticated",
                403: "forbidden",
                404: "not_found",
            }[expected]
        )
    if expected == 401:
        assert response.headers["www-authenticate"] == "Bearer"


def _route_contexts(app):
    """Every effective route, with included routers flattened.

    FastAPI >= 0.160 keeps included routers as lazy ``_IncludedRouter`` entries in
    ``app.routes``, so a plain walk would silently miss every ``/api/v1`` route;
    ``iter_route_contexts`` is the same public iterator OpenAPI generation uses.
    """
    return list(iter_route_contexts(app.routes))


def _app_routes(app) -> set[tuple[str, str]]:
    """Every (method, path) the app serves, excluding the implicit HEAD."""
    return {
        (method, context.path)
        for context in _route_contexts(app)
        for method in (context.methods or set())
        if method != "HEAD"
    }


def test_route_walk_sees_the_versioned_api(client):
    assert ("GET", f"{API}/users/me") in _app_routes(client.app)


def test_every_route_is_in_the_matrix_or_explicitly_public(client):
    covered = {(method, API + path) for method, path in MATRIX} | PUBLIC

    uncovered = _app_routes(client.app) - covered

    assert not uncovered, f"Routes without an authorization decision: {sorted(uncovered)}"


def test_matrix_has_no_stale_entries(client):
    served = _app_routes(client.app)

    stale = {(m, API + p) for m, p in MATRIX if (m, API + p) not in served} | (PUBLIC - served)

    assert not stale, f"Matrix/PUBLIC entries for routes that no longer exist: {sorted(stale)}"


def test_every_non_public_api_route_requires_the_current_user(client):
    from team_notes_api.api.deps import get_current_user

    def depends_on_current_user(dependant) -> bool:
        return any(
            dep.call is get_current_user or depends_on_current_user(dep)
            for dep in dependant.dependencies
        )

    missing = [
        (method, context.path)
        for context in _route_contexts(client.app)
        if isinstance(context.original_route, APIRoute)
        for method in context.methods or set()
        if (method, context.path) not in PUBLIC and not depends_on_current_user(context.dependant)
    ]

    assert not missing, f"Routes that never resolve CurrentUser: {missing}"


def test_notes_are_only_loaded_through_the_chokepoint():
    """Only services/notes.py may query the Note model; every by-id load goes through
    ``get_note_for_user`` there. A ``select(Note ...)`` or ``.get(Note, ...)`` anywhere
    else would be a second, unguarded way to read a note."""
    package = Path(team_notes_api.__file__).parent
    allowed = package / "services" / "notes.py"
    offenders = []
    for path in package.rglob("*.py"):
        if path == allowed:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, (ast.Name, ast.Attribute))
                and getattr(node.func, "id", getattr(node.func, "attr", None))
                in {"select", "get", "update", "delete"}
                and any(isinstance(arg, ast.Name) and arg.id == "Note" for arg in node.args)
            ):
                offenders.append(f"{path.relative_to(package)}:{node.lineno}")

    assert not offenders, f"Note queried outside services/notes.py: {offenders}"

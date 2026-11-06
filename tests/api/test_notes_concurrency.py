"""Optimistic concurrency on note edits: one atomic versioned UPDATE, 409 on stale versions."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import API, auth, make_note, make_team, make_user
from fastapi.testclient import TestClient


@pytest.fixture
def note_ctx(client):
    """A user, their token and one note (version 1) with tags ``a``, ``b``."""
    _, token = make_user(client, "ada@example.com")
    team = make_team(client, token)
    note = make_note(client, token, team["id"], title="T", body="B", tags=["a", "b"])
    return token, note


def patch(client, token, note_id, payload):
    """PATCH a note and return the response."""
    return client.patch(f"{API}/notes/{note_id}", json=payload, headers=auth(token))


def test_stale_version_is_409_with_current_version_and_changes_nothing(client, note_ctx):
    token, note = note_ctx
    assert patch(client, token, note["id"], {"version": 1, "title": "v2"}).status_code == 200

    stale = patch(client, token, note["id"], {"version": 1, "title": "lost", "tags": ["z"]})

    assert stale.status_code == 409
    error = stale.json()["error"]
    assert error["code"] == "version_conflict"
    assert error["details"] == {"current_version": 2}
    current = client.get(f"{API}/notes/{note['id']}", headers=auth(token)).json()["data"]
    assert (current["title"], current["tags"], current["version"]) == ("v2", ["a", "b"], 2)


def test_two_edits_of_the_same_version_yield_exactly_one_success(client, note_ctx):
    token, note = note_ctx

    first = patch(client, token, note["id"], {"version": 1, "body": "first"})
    second = patch(client, token, note["id"], {"version": 1, "body": "second"})

    assert sorted([first.status_code, second.status_code]) == [200, 409]
    current = client.get(f"{API}/notes/{note['id']}", headers=auth(token)).json()["data"]
    assert (current["body"], current["version"]) == ("first", 2)


@pytest.mark.parametrize("racers", [2, 3, 4])
def test_racing_edits_of_the_same_version_yield_exactly_one_success(client, note_ctx, racers):
    """Real concurrency: N threads released together by a barrier, each with its own
    TestClient over the same app and temp-file SQLite database, all PATCH version 1.

    The conditional UPDATE is the only arbiter: SQLite serializes the writers (WAL +
    busy_timeout), the first to commit matches ``version = 1``, and every later one
    matches zero rows and must get 409, never a 500 or a second 200.
    """
    token, note = note_ctx
    barrier = threading.Barrier(racers)

    def edit(index: int):
        with TestClient(client.app) as racer:
            barrier.wait(timeout=10)
            return patch(racer, token, note["id"], {"version": 1, "body": f"racer {index}"})

    with ThreadPoolExecutor(max_workers=racers) as pool:
        responses = list(pool.map(edit, range(racers)))

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200] + [409] * (racers - 1), [r.text for r in responses]
    for conflict in (r for r in responses if r.status_code == 409):
        assert conflict.json()["error"] == {
            "code": "version_conflict",
            "message": conflict.json()["error"]["message"],
            "details": {"current_version": 2},
        }
    winner = next(r for r in responses if r.status_code == 200).json()["data"]
    current = client.get(f"{API}/notes/{note['id']}", headers=auth(token)).json()["data"]
    assert current["version"] == 2
    assert current["body"] == winner["body"]


def test_tags_only_change_bumps_version_and_replaces_tags(client, note_ctx):
    token, note = note_ctx

    response = patch(client, token, note["id"], {"version": 1, "tags": ["C", "b", "c"]})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["version"] == 2
    assert data["tags"] == ["b", "c"]
    assert data["title"] == "T"


def test_clearing_tags_is_an_edit(client, note_ctx):
    token, note = note_ctx

    response = patch(client, token, note["id"], {"version": 1, "tags": []})

    assert response.status_code == 200
    assert response.json()["data"]["tags"] == []
    assert response.json()["data"]["version"] == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 1},
        {"title": "no version"},
        {"version": 0, "title": "x"},
        {"version": 1, "title": None},
        {"version": 1, "tags": None},
        {"version": 1, "team_id": 2},
    ],
)
def test_patch_without_an_editable_field_or_version_is_422(client, note_ctx, payload):
    token, note = note_ctx

    response = patch(client, token, note["id"], payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_version_conflict_on_a_vanished_note_is_404(client, note_ctx):
    token, note = note_ctx
    assert client.delete(f"{API}/notes/{note['id']}", headers=auth(token)).status_code == 204

    response = patch(client, token, note["id"], {"version": 1, "title": "x"})

    assert response.status_code == 404

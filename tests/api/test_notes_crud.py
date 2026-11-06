"""Note CRUD through the single authorization chokepoint."""

import pytest
from conftest import API, add_member, auth, make_note, make_team, make_user
from sqlalchemy import func, select

from team_notes_api.models import NoteTag


@pytest.fixture
def world(client):
    """An owner and a member sharing a team, plus an outsider in another team."""
    owner, owner_token = make_user(client, "owner@example.com", "Owner")
    member, member_token = make_user(client, "member@example.com", "Member")
    _, outsider_token = make_user(client, "outsider@example.com", "Outsider")
    team = make_team(client, owner_token, "Platform")
    assert add_member(client, owner_token, team["id"], "member@example.com").status_code == 201
    make_team(client, outsider_token, "Elsewhere")
    return {
        "team": team,
        "owner": (owner, owner_token),
        "member": (member, member_token),
        "outsider_token": outsider_token,
    }


def test_create_note_returns_201_location_and_normalized_tags(client, world):
    owner, token = world["owner"]

    response = client.post(
        f"{API}/teams/{world['team']['id']}/notes",
        json={"title": "  Plan  ", "body": "Ship it", "tags": [" Ops", "ops", "Q3 "]},
        headers=auth(token),
    )

    assert response.status_code == 201
    note = response.json()["data"]
    assert response.headers["location"] == f"/api/v1/notes/{note['id']}"
    assert note["title"] == "Plan"
    assert note["tags"] == ["ops", "q3"]
    assert note["version"] == 1
    assert note["created_by_id"] == note["updated_by_id"] == owner["id"]
    assert note["created_at"].endswith("Z") and note["updated_at"].endswith("Z")


def test_member_reads_a_note_created_by_the_owner(client, world):
    _, owner_token = world["owner"]
    _, member_token = world["member"]
    note = make_note(client, owner_token, world["team"]["id"], title="Shared")

    response = client.get(f"{API}/notes/{note['id']}", headers=auth(member_token))

    assert response.status_code == 200
    assert response.json()["data"] == note


def test_member_edits_any_note(client, world):
    _, owner_token = world["owner"]
    member, member_token = world["member"]
    note = make_note(client, owner_token, world["team"]["id"], title="Old")

    response = client.patch(
        f"{API}/notes/{note['id']}",
        json={"version": 1, "title": "New", "body": "Body"},
        headers=auth(member_token),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["title"], data["body"], data["version"]) == ("New", "Body", 2)
    assert data["updated_by_id"] == member["id"]
    assert data["updated_at"] >= note["updated_at"]


@pytest.mark.parametrize(
    "payload",
    [
        {"title": ""},
        {"title": "x" * 201},
        {"body": "x" * 100_001},
        {"tags": ["x" * 33]},
        {"tags": ["   "]},
        {"tags": [f"t{i}" for i in range(21)]},
        {"title": "ok", "extra": 1},
    ],
)
def test_invalid_note_payloads_are_422(client, world, payload):
    _, token = world["owner"]
    body = {"title": "ok"} | payload

    response = client.post(
        f"{API}/teams/{world['team']['id']}/notes", json=body, headers=auth(token)
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_non_member_gets_404_on_get_patch_and_delete(client, world):
    _, owner_token = world["owner"]
    outsider = auth(world["outsider_token"])
    note = make_note(client, owner_token, world["team"]["id"])
    url = f"{API}/notes/{note['id']}"

    responses = [
        client.get(url, headers=outsider),
        client.patch(url, json={"version": 1, "title": "x"}, headers=outsider),
        client.delete(url, headers=outsider),
    ]
    missing = client.get(f"{API}/notes/999999", headers=outsider)

    assert [r.status_code for r in responses] == [404, 404, 404]
    assert all(r.json() == missing.json() for r in responses)
    still_there = client.get(url, headers=auth(owner_token))
    assert still_there.json()["data"]["version"] == 1


def test_non_member_cannot_create_notes_in_the_team(client, world):
    response = client.post(
        f"{API}/teams/{world['team']['id']}/notes",
        json={"title": "x"},
        headers=auth(world["outsider_token"]),
    )

    assert response.status_code == 404


def test_member_cannot_delete_someone_elses_note(client, world):
    _, owner_token = world["owner"]
    _, member_token = world["member"]
    note = make_note(client, owner_token, world["team"]["id"])

    response = client.delete(f"{API}/notes/{note['id']}", headers=auth(member_token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_member_deletes_own_note(client, world):
    _, member_token = world["member"]
    note = make_note(client, member_token, world["team"]["id"])

    response = client.delete(f"{API}/notes/{note['id']}", headers=auth(member_token))

    assert response.status_code == 204


def test_owner_deletes_a_members_note_and_tags_cascade(client, world):
    _, owner_token = world["owner"]
    _, member_token = world["member"]
    note = make_note(client, member_token, world["team"]["id"], tags=["a", "b"])

    response = client.delete(f"{API}/notes/{note['id']}", headers=auth(owner_token))

    assert response.status_code == 204
    assert client.get(f"{API}/notes/{note['id']}", headers=auth(owner_token)).status_code == 404
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(NoteTag)) == 0


def test_leaving_a_team_revokes_note_access(client, world):
    _, owner_token = world["owner"]
    member, member_token = world["member"]
    note = make_note(client, owner_token, world["team"]["id"])
    client.delete(
        f"{API}/teams/{world['team']['id']}/members/{member['id']}", headers=auth(member_token)
    )

    response = client.get(f"{API}/notes/{note['id']}", headers=auth(member_token))

    assert response.status_code == 404

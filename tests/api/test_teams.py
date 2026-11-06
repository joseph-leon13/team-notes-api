"""Teams and membership: creation, visibility, adding/removing members, last-owner guard."""

import pytest
from conftest import API, add_member, auth, make_team, make_user


@pytest.fixture
def people(client):
    """Three registered users: an owner, a future member and an outsider."""
    owner, owner_token = make_user(client, "owner@example.com", "Owner")
    member, member_token = make_user(client, "member@example.com", "Member")
    outsider, outsider_token = make_user(client, "outsider@example.com", "Outsider")
    return {
        "owner": (owner, owner_token),
        "member": (member, member_token),
        "outsider": (outsider, outsider_token),
    }


@pytest.fixture
def team(client, people):
    """A team owned by ``owner`` with ``member`` as a plain member."""
    _, owner_token = people["owner"]
    created = make_team(client, owner_token, "Platform")
    assert add_member(client, owner_token, created["id"], "member@example.com").status_code == 201
    return created


def test_create_team_makes_creator_owner(client, people):
    owner, token = people["owner"]

    team = make_team(client, token, "  Platform  ")
    detail = client.get(f"{API}/teams/{team['id']}", headers=auth(token)).json()["data"]

    assert team["name"] == "Platform"
    assert team["role"] == "owner"
    assert team["created_at"].endswith("Z")
    assert [(m["user_id"], m["role"]) for m in detail["members"]] == [(owner["id"], "owner")]


def test_list_teams_returns_only_my_teams(client, people):
    _, owner_token = people["owner"]
    _, outsider_token = people["outsider"]
    mine = make_team(client, owner_token, "Mine")
    make_team(client, outsider_token, "Theirs")

    response = client.get(f"{API}/teams", headers=auth(owner_token))

    assert response.status_code == 200
    assert [t["id"] for t in response.json()["data"]] == [mine["id"]]


def test_get_team_is_404_for_non_members(client, people, team):
    _, outsider_token = people["outsider"]

    response = client.get(f"{API}/teams/{team['id']}", headers=auth(outsider_token))
    missing = client.get(f"{API}/teams/99999", headers=auth(outsider_token))

    assert response.status_code == 404
    assert response.json() == missing.json()


def test_owner_adds_member_with_default_role(client, people, team):
    _, owner_token = people["owner"]

    detail = client.get(f"{API}/teams/{team['id']}", headers=auth(owner_token)).json()["data"]

    roles = {m["email"]: m["role"] for m in detail["members"]}
    assert roles == {"owner@example.com": "owner", "member@example.com": "member"}


def test_member_cannot_add_members(client, people, team):
    _, member_token = people["member"]

    response = add_member(client, member_token, team["id"], "outsider@example.com")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_non_member_adding_members_gets_404(client, people, team):
    _, outsider_token = people["outsider"]

    response = add_member(client, outsider_token, team["id"], "outsider@example.com")

    assert response.status_code == 404


def test_adding_unknown_email_is_404(client, people, team):
    _, owner_token = people["owner"]

    response = add_member(client, owner_token, team["id"], "ghost@example.com")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_adding_existing_member_is_409(client, people, team):
    _, owner_token = people["owner"]

    response = add_member(client, owner_token, team["id"], "MEMBER@example.com")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_invalid_role_is_422(client, people, team):
    _, owner_token = people["owner"]

    response = add_member(client, owner_token, team["id"], "outsider@example.com", role="admin")

    assert response.status_code == 422


def test_owner_removes_member(client, people, team):
    _, owner_token = people["owner"]
    member, member_token = people["member"]

    response = client.delete(
        f"{API}/teams/{team['id']}/members/{member['id']}", headers=auth(owner_token)
    )

    assert response.status_code == 204
    assert response.content == b""
    gone = client.get(f"{API}/teams/{team['id']}", headers=auth(member_token))
    assert gone.status_code == 404


def test_member_can_leave(client, people, team):
    member, member_token = people["member"]

    response = client.delete(
        f"{API}/teams/{team['id']}/members/{member['id']}", headers=auth(member_token)
    )

    assert response.status_code == 204
    assert client.get(f"{API}/teams", headers=auth(member_token)).json()["data"] == []


def test_member_cannot_remove_someone_else(client, people, team):
    owner, _ = people["owner"]
    _, member_token = people["member"]

    response = client.delete(
        f"{API}/teams/{team['id']}/members/{owner['id']}", headers=auth(member_token)
    )

    assert response.status_code == 403


def test_removing_a_non_member_is_404(client, people, team):
    _, owner_token = people["owner"]
    outsider, _ = people["outsider"]

    response = client.delete(
        f"{API}/teams/{team['id']}/members/{outsider['id']}", headers=auth(owner_token)
    )

    assert response.status_code == 404


def test_last_owner_cannot_leave(client, people, team):
    owner, owner_token = people["owner"]

    response = client.delete(
        f"{API}/teams/{team['id']}/members/{owner['id']}", headers=auth(owner_token)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_owner"


def test_an_owner_can_leave_when_another_owner_remains(client, people, team):
    owner, owner_token = people["owner"]
    second, second_token = people["outsider"]
    assert add_member(client, owner_token, team["id"], second["email"], "owner").status_code == 201

    leave = client.delete(
        f"{API}/teams/{team['id']}/members/{owner['id']}", headers=auth(owner_token)
    )
    last = client.delete(
        f"{API}/teams/{team['id']}/members/{second['id']}", headers=auth(second_token)
    )

    assert leave.status_code == 204
    assert last.status_code == 409
    assert last.json()["error"]["code"] == "last_owner"


@pytest.mark.parametrize("email", ["no-at-sign", "user@", "has space@example.com"])
def test_add_member_with_invalid_email_is_422(client, people, team, email):
    _, owner_token = people["owner"]

    response = add_member(client, owner_token, team["id"], email)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_add_member_matches_email_case_insensitively(client, people, team):
    _, owner_token = people["owner"]

    response = add_member(client, owner_token, team["id"], "  OUTSIDER@Example.com ")

    assert response.status_code == 201
    assert response.json()["data"]["email"] == "outsider@example.com"

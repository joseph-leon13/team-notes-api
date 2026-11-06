"""User registration and bearer-token identity."""

from sqlalchemy import select

from team_notes_api.models import User
from team_notes_api.security import hash_token
from tests.helpers import API, auth, register


def test_create_user_returns_user_and_token_once(client):
    response = client.post(
        f"{API}/users", json={"email": "  Ada@Example.COM ", "display_name": " Ada "}
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"data", "meta"}
    user = body["data"]["user"]
    assert user["email"] == "ada@example.com"
    assert user["display_name"] == "Ada"
    assert user["created_at"].endswith("Z")
    assert "token_hash" not in user
    assert len(body["data"]["token"]) >= 40


def test_token_is_stored_only_as_its_digest(client):
    _, token = register(client, "ada@example.com")

    with client.app.state.session_factory() as session:
        stored = session.scalars(select(User.token_hash)).one()

    assert stored == hash_token(token)
    assert token not in stored


def test_duplicate_email_is_a_conflict_regardless_of_case(client):
    register(client, "ada@example.com")

    response = client.post(f"{API}/users", json={"email": "ADA@example.com", "display_name": "X"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_invalid_email_and_unknown_fields_are_rejected(client):
    bad_email = client.post(f"{API}/users", json={"email": "nope", "display_name": "X"})
    extra = client.post(
        f"{API}/users", json={"email": "a@b.co", "display_name": "X", "is_admin": True}
    )

    assert bad_email.status_code == 422
    assert extra.status_code == 422
    assert extra.json()["error"]["code"] == "validation_error"


def test_me_returns_the_token_owner(client):
    user, token = register(client, "ada@example.com", "Ada")
    register(client, "bob@example.com", "Bob")

    response = client.get(f"{API}/users/me", headers=auth(token))

    assert response.status_code == 200
    assert response.json()["data"] == user


def test_me_without_token_is_401_with_bearer_challenge(client):
    response = client.get(f"{API}/users/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthenticated"


def test_me_with_bad_token_is_401(client):
    register(client, "ada@example.com")

    bad_token = client.get(f"{API}/users/me", headers=auth("not-a-real-token"))
    wrong_scheme = client.get(f"{API}/users/me", headers={"Authorization": "Basic abc"})

    for response in (bad_token, wrong_scheme):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["error"]["code"] == "unauthenticated"

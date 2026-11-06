"""User registration and bearer-token identity."""

import pytest
from conftest import API, auth, make_user
from sqlalchemy import select

from team_notes_api.core.security import hash_token
from team_notes_api.models import User


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
    _, token = make_user(client, "ada@example.com")

    with client.app.state.session_factory() as session:
        stored = session.scalars(select(User.token_hash)).one()

    assert stored == hash_token(token)
    assert token not in stored


def test_duplicate_email_is_a_conflict_regardless_of_case(client):
    make_user(client, "ada@example.com")

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
    user, token = make_user(client, "ada@example.com", "Ada")
    make_user(client, "bob@example.com", "Bob")

    response = client.get(f"{API}/users/me", headers=auth(token))

    assert response.status_code == 200
    assert response.json()["data"] == user


def test_me_without_token_is_401_with_bearer_challenge(client):
    response = client.get(f"{API}/users/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthenticated"


def test_me_with_bad_token_is_401(client):
    make_user(client, "ada@example.com")

    bad_token = client.get(f"{API}/users/me", headers=auth("not-a-real-token"))
    wrong_scheme = client.get(f"{API}/users/me", headers={"Authorization": "Basic abc"})

    for response in (bad_token, wrong_scheme):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["error"]["code"] == "unauthenticated"


INVALID_EMAILS = ["no-at-sign", "user@", "@example.com", "has space@example.com", "a@b", ""]


@pytest.mark.parametrize("email", INVALID_EMAILS)
def test_invalid_email_is_422_validation_error(client, email):
    response = client.post(f"{API}/users", json={"email": email, "display_name": "X"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert ["body", "email"] in [item["loc"] for item in error["details"]["errors"]]


def test_mixed_case_email_is_stored_lower_cased(client):
    make_user(client, "Grace.Hopper@Navy.MIL")

    with client.app.state.session_factory() as session:
        stored = session.scalars(select(User.email)).one()

    assert stored == "grace.hopper@navy.mil"


def test_email_validation_does_no_dns_lookups(client, monkeypatch):
    import email_validator.deliverability

    def no_dns(*args, **kwargs):
        raise AssertionError("email validation must not run deliverability (DNS) checks")

    monkeypatch.setattr(email_validator.deliverability, "validate_email_deliverability", no_dns)

    _, token = make_user(client, "someone@unregistered-domain-for-tests.dev")

    assert token

"""Note listing: keyset pagination, tag AND filter and escaped substring search."""

from datetime import UTC, datetime

import pytest
from conftest import API, auth, make_note, make_team, make_user
from sqlalchemy import update

from team_notes_api.models import Note


@pytest.fixture
def team_ctx(client):
    """A user, their token and an empty team."""
    _, token = make_user(client, "ada@example.com")
    team = make_team(client, token)
    return token, team["id"]


def list_notes(client, token, team_id, **params):
    """GET the team's notes with query ``params`` and return the response."""
    return client.get(f"{API}/teams/{team_id}/notes", params=params, headers=auth(token))


def collect_all(client, token, team_id, limit):
    """Follow ``next_cursor`` to the end and return (all ids, page sizes)."""
    ids, sizes, cursor = [], [], None
    while True:
        params = {"limit": limit} | ({"cursor": cursor} if cursor else {})
        body = list_notes(client, token, team_id, **params).json()
        ids += [note["id"] for note in body["data"]]
        sizes.append(len(body["data"]))
        assert body["meta"]["has_more"] is (body["meta"]["next_cursor"] is not None)
        cursor = body["meta"]["next_cursor"]
        if cursor is None:
            return ids, sizes


def test_pages_have_no_gaps_or_duplicates_when_timestamps_tie(client, team_ctx):
    token, team_id = team_ctx
    created = [make_note(client, token, team_id, title=f"n{i}")["id"] for i in range(25)]
    tied = datetime(2026, 1, 1, 12, 0, 0, 123456, tzinfo=UTC)
    with client.app.state.session_factory() as session:
        session.execute(update(Note).values(updated_at=tied))
        session.commit()

    ids, sizes = collect_all(client, token, team_id, limit=10)

    assert sizes == [10, 10, 5]
    assert ids == sorted(created, reverse=True)


def test_order_is_most_recently_updated_first(client, team_ctx):
    token, team_id = team_ctx
    first = make_note(client, token, team_id, title="first")
    second = make_note(client, token, team_id, title="second")
    client.patch(
        f"{API}/notes/{first['id']}", json={"version": 1, "body": "x"}, headers=auth(token)
    )

    ids, _ = collect_all(client, token, team_id, limit=1)

    assert ids == [first["id"], second["id"]]


def test_default_page_meta(client, team_ctx):
    token, team_id = team_ctx
    make_note(client, token, team_id)

    body = list_notes(client, token, team_id).json()

    assert body["meta"] == {"limit": 20, "next_cursor": None, "has_more": False}
    assert body["data"][0]["updated_at"].endswith("Z")


@pytest.mark.parametrize("limit", [0, 101, -1, "abc"])
def test_limit_out_of_bounds_is_422(client, team_ctx, limit):
    token, team_id = team_ctx

    response = list_notes(client, token, team_id, limit=limit)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("limit", [1, 100])
def test_limit_bounds_are_inclusive(client, team_ctx, limit):
    token, team_id = team_ctx

    response = list_notes(client, token, team_id, limit=limit)

    assert response.status_code == 200
    assert response.json()["meta"]["limit"] == limit


@pytest.mark.parametrize(
    "cursor",
    [
        "not-base64!!",
        "e30",  # {}
        "eyJ1Ijoibm9wZSIsImkiOjF9",  # {"u":"nope","i":1}
        "eyJ1IjoiMjAyNi0wMS0wMVQwMDowMDowMCIsImkiOjF9",  # naive timestamp
        "eyJ1IjoiMjAyNi0wMS0wMVQwMDowMDowMCswMDowMCIsImkiOiIxIn0",  # string id
        "W10",  # []
    ],
)
def test_malformed_cursor_is_422_invalid_cursor(client, team_ctx, cursor):
    token, team_id = team_ctx

    response = list_notes(client, token, team_id, cursor=cursor)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_search_is_case_insensitive_on_title_or_body(client, team_ctx):
    token, team_id = team_ctx
    in_title = make_note(client, token, team_id, title="Quarterly PLAN")
    in_body = make_note(client, token, team_id, title="Other", body="the plan is")
    make_note(client, token, team_id, title="Unrelated")

    body = list_notes(client, token, team_id, q="plan").json()

    assert {n["id"] for n in body["data"]} == {in_title["id"], in_body["id"]}


def test_search_treats_percent_and_underscore_literally(client, team_ctx):
    token, team_id = team_ctx
    literal = make_note(client, token, team_id, title="100% done")
    make_note(client, token, team_id, title="1000 done")
    underscore = make_note(client, token, team_id, title="snake_case")
    make_note(client, token, team_id, title="snakeXcase")

    percent = list_notes(client, token, team_id, q="0%").json()["data"]
    under = list_notes(client, token, team_id, q="e_c").json()["data"]

    assert [n["id"] for n in percent] == [literal["id"]]
    assert [n["id"] for n in under] == [underscore["id"]]


def test_q_longer_than_100_chars_is_422(client, team_ctx):
    token, team_id = team_ctx

    assert list_notes(client, token, team_id, q="x" * 101).status_code == 422


def test_repeated_tag_filters_are_anded_without_duplicates(client, team_ctx):
    token, team_id = team_ctx
    both = make_note(client, token, team_id, tags=["ops", "urgent", "q3"])
    make_note(client, token, team_id, tags=["ops"])
    make_note(client, token, team_id, tags=["urgent"])

    and_body = client.get(
        f"{API}/teams/{team_id}/notes?tag=ops&tag=URGENT", headers=auth(token)
    ).json()
    one_tag = list_notes(client, token, team_id, tag="ops").json()

    assert [n["id"] for n in and_body["data"]] == [both["id"]]
    assert len(one_tag["data"]) == 2
    assert len({n["id"] for n in one_tag["data"]}) == 2


def test_listing_is_scoped_to_the_team(client, team_ctx):
    token, team_id = team_ctx
    other_team = make_team(client, token, "Other")
    make_note(client, token, other_team["id"], title="elsewhere")
    mine = make_note(client, token, team_id, title="here")

    body = list_notes(client, token, team_id).json()

    assert [n["id"] for n in body["data"]] == [mine["id"]]


def test_non_member_listing_is_404(client, team_ctx):
    _, team_id = team_ctx
    _, outsider_token = make_user(client, "out@example.com")

    assert list_notes(client, outsider_token, team_id).status_code == 404

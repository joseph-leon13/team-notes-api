"""Unit tests for the opaque keyset cursor."""

import base64
import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from team_notes_api.core.errors import InvalidCursorError
from team_notes_api.models import Note
from team_notes_api.services.notes import decode_cursor, encode_cursor


def _encode(payload) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def test_cursor_round_trips_microseconds_and_id():
    note = Note(id=42, updated_at=datetime(2026, 3, 4, 5, 6, 7, 891011, tzinfo=UTC))

    cursor = encode_cursor(note)

    assert "=" not in cursor
    assert decode_cursor(cursor) == (note.updated_at, 42)


def test_decoded_timestamp_is_normalized_to_utc():
    plus_two = timezone(timedelta(hours=2))
    cursor = _encode({"u": datetime(2026, 1, 1, 14, tzinfo=plus_two).isoformat(), "i": 1})

    updated_at, _ = decode_cursor(cursor)

    assert updated_at == datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert updated_at.tzinfo is UTC


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "%%%",
        base64.urlsafe_b64encode(b"\xff\xfe").decode(),
        _encode([]),
        _encode({"u": "2026-01-01T00:00:00+00:00"}),
        _encode({"u": "2026-01-01T00:00:00", "i": 1}),
        _encode({"u": "2026-01-01T00:00:00+00:00", "i": "1"}),
        _encode({"u": "2026-01-01T00:00:00+00:00", "i": True}),
        _encode({"u": 123, "i": 1}),
    ],
)
def test_malformed_cursors_raise_invalid_cursor(cursor):
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor)

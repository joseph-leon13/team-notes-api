"""Custom column types shared by the ORM models."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


def utc_now() -> datetime:
    """Return the current time as an aware UTC datetime (microsecond precision)."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """A ``DateTime`` that only accepts aware datetimes and always returns UTC-aware ones.

    SQLite has no timezone-aware type and hands back naive values, so values are stored
    as naive UTC and re-tagged with ``UTC`` on the way out. Naive input is rejected
    rather than guessed at.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Convert an aware datetime to naive UTC for storage."""
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UTCDateTime requires a timezone-aware datetime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Tag a stored naive UTC datetime as UTC."""
        return value.replace(tzinfo=UTC) if value is not None else None

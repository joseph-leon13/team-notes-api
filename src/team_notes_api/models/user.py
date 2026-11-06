"""The ``User`` model: an identity that authenticates with a hashed bearer token."""

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from team_notes_api.core.db import Base
from team_notes_api.models.types import UTCDateTime, utc_now


class User(Base):
    """A person using the service.

    ``token_hash`` is the sha256 hexdigest of the bearer token; the plaintext token is
    never stored. It is unique and indexed so authentication is a single lookup.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

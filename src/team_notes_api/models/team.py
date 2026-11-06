"""The ``Team`` and ``Membership`` models, and the ``Role`` a member holds."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from team_notes_api.core.db import Base
from team_notes_api.models.types import UTCDateTime, utc_now
from team_notes_api.models.user import User


class Role(StrEnum):
    """A member's role inside one team."""

    OWNER = "owner"
    MEMBER = "member"


class Team(Base):
    """A small group of users who share notes."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="team", cascade="all, delete-orphan", passive_deletes=True
    )


class Membership(Base):
    """A user's membership in a team; the unit every authorization check joins on."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_memberships_team_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # a Role value
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    team: Mapped[Team] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()

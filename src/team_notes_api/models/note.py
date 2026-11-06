"""The ``Note`` model and its ``NoteTag`` child rows."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from team_notes_api.db import Base
from team_notes_api.models.types import UTCDateTime, utc_now


class Note(Base):
    """A note owned by a team.

    ``version`` drives optimistic concurrency: every successful edit increments it, and
    an edit is applied only if the client's version still matches.
    The ``(team_id, updated_at, id)`` index serves the keyset-paginated listing.
    """

    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_team_updated_id", "team_id", "updated_at", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    tags: Mapped[list["NoteTag"]] = relationship(
        back_populates="note",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="NoteTag.tag",
    )


class NoteTag(Base):
    """One tag on one note. The composite primary key makes duplicates impossible."""

    __tablename__ = "note_tags"

    note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)

    note: Mapped[Note] = relationship(back_populates="tags")

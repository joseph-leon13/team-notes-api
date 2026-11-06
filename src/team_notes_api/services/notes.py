"""Notes: the authorization chokepoint and note create/read/delete.

:func:`get_note_for_user` is the ONLY way to load a note by id. It joins ``notes`` to
the caller's ``memberships`` row, so "no such note" and "note in a team you are not in"
are the same empty result and the same 404: a note's existence never leaks.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from team_notes_api.core.errors import ForbiddenError, NotFoundError
from team_notes_api.models import Membership, Note, NoteTag, User
from team_notes_api.models.types import utc_now
from team_notes_api.services import policy
from team_notes_api.services.teams import get_membership_or_404


@dataclass(frozen=True)
class VisibleNote:
    """A note together with the caller's role in the note's team."""

    note: Note
    role: str


def get_note_for_user(session: Session, note_id: int, user: User) -> VisibleNote:
    """Load a note the caller can see, with their role, or raise 404.

    Always re-reads the row (``populate_existing``) so callers never see stale state
    from the session's identity map after a bulk UPDATE.
    """
    row = session.execute(
        select(Note, Membership.role)
        .join(
            Membership,
            (Membership.team_id == Note.team_id) & (Membership.user_id == user.id),
        )
        .where(Note.id == note_id)
        .options(selectinload(Note.tags))
        .execution_options(populate_existing=True)
    ).one_or_none()
    if row is None:
        raise NotFoundError("Note not found.")
    note, role = row
    if not policy.can_read_note(role):
        raise ForbiddenError()
    return VisibleNote(note=note, role=role)


def create_note(
    session: Session, team_id: int, user: User, title: str, body: str, tags: list[str]
) -> Note:
    """Create a note in a team the caller belongs to."""
    membership = get_membership_or_404(session, team_id, user)
    if not policy.can_create_note(membership.role):
        raise ForbiddenError()

    now = utc_now()
    note = Note(
        team_id=team_id,
        title=title,
        body=body,
        created_by_id=user.id,
        updated_by_id=user.id,
        created_at=now,
        updated_at=now,
        tags=[NoteTag(tag=tag) for tag in tags],
    )
    session.add(note)
    session.commit()
    return note


def delete_note(session: Session, note_id: int, user: User) -> None:
    """Delete a note. Allowed for its creator or a team owner; tags cascade."""
    visible = get_note_for_user(session, note_id, user)
    if not policy.can_delete_note(visible.role, user.id, visible.note.created_by_id):
        raise ForbiddenError("Only the note's creator or a team owner can delete it.")
    session.delete(visible.note)
    session.commit()

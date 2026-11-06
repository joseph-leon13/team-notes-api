"""Note endpoints. Every endpoint requires a bearer token.

Two routers, both tagged ``notes``: ``team_notes_router`` owns the team-scoped
collection (``/teams/{team_id}/notes``), ``router`` owns single notes (``/notes/{id}``).
"""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from team_notes_api.api.deps import CurrentUser, PageParams
from team_notes_api.core.db import SessionDep
from team_notes_api.schemas.common import Envelope, PageEnvelope, PageMeta, error_responses
from team_notes_api.schemas.notes import MAX_TAG_LENGTH, NoteCreate, NoteOut, NoteUpdate
from team_notes_api.services import notes as note_service

router = APIRouter(prefix="/notes", tags=["notes"])
team_notes_router = APIRouter(prefix="/teams/{team_id}/notes", tags=["notes"])

TagFilter = Annotated[
    list[Annotated[str, Query(min_length=1, max_length=MAX_TAG_LENGTH)]],
    Query(description="Repeatable; a note must carry every given tag (AND)."),
]
SearchQuery = Annotated[
    str | None,
    Query(max_length=100, description="Case-insensitive substring of title or body."),
]


@team_notes_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a note in a team",
    responses=error_responses(401, 404, 422),
)
def create_note(
    team_id: int,
    payload: NoteCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> Envelope[NoteOut]:
    """Create a note. Tags are trimmed, lower-cased and de-duplicated.

    The `Location` header points at the new note.
    """
    note = note_service.create_note(
        session, team_id, user, payload.title, payload.body, payload.tags
    )
    response.headers["Location"] = f"/api/v1/notes/{note.id}"
    return Envelope(data=NoteOut.model_validate(note))


@team_notes_router.get(
    "",
    summary="List a team's notes",
    responses=error_responses(
        401, 404, 422, s422="Invalid parameter (`validation_error`) or cursor (`invalid_cursor`)."
    ),
)
def list_notes(
    team_id: int,
    page: PageParams,
    session: SessionDep,
    user: CurrentUser,
    q: SearchQuery = None,
    tag: TagFilter = [],  # noqa: B006 (FastAPI copies defaults per request)
) -> PageEnvelope[NoteOut]:
    """List notes, most recently updated first, using keyset (cursor) pagination.

    Pass `meta.next_cursor` back as `cursor` to get the next page; it is null on the last.
    """
    tags = [t.strip().lower() for t in tag]
    result = note_service.list_notes(
        session, team_id, user, limit=page.limit, cursor=page.cursor, q=q or None, tags=tags
    )
    return PageEnvelope(
        data=[NoteOut.model_validate(note) for note in result.notes],
        meta=PageMeta(
            limit=page.limit,
            next_cursor=result.next_cursor,
            has_more=result.next_cursor is not None,
        ),
    )


@router.get("/{note_id}", summary="Get a note", responses=error_responses(401, 404, 422))
def get_note(note_id: int, session: SessionDep, user: CurrentUser) -> Envelope[NoteOut]:
    """Return a note from one of the caller's teams. Anything else is 404."""
    visible = note_service.get_note_for_user(session, note_id, user)
    return Envelope(data=NoteOut.model_validate(visible.note))


@router.patch(
    "/{note_id}",
    summary="Edit a note (optimistic concurrency)",
    responses=error_responses(
        401,
        404,
        409,
        422,
        s409="`version` is stale (`version_conflict`); `details.current_version` has the latest.",
    ),
)
def update_note(
    note_id: int, payload: NoteUpdate, session: SessionDep, user: CurrentUser
) -> Envelope[NoteOut]:
    """Edit title, body and/or tags. Send the `version` you last read.

    On success the version increments (a tags-only edit too). If someone edited the note
    since, nothing is changed and you get 409 with the current version.
    """
    note = note_service.update_note(session, note_id, user, payload.version, payload.changes())
    return Envelope(data=NoteOut.model_validate(note))


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a note",
    responses=error_responses(
        401, 403, 404, 422, s403="Caller is neither the creator nor a team owner (`forbidden`)."
    ),
)
def delete_note(note_id: int, session: SessionDep, user: CurrentUser) -> Response:
    """Delete a note. Allowed for the note's creator or an owner of its team."""
    note_service.delete_note(session, note_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

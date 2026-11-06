"""User endpoints. ``POST /users`` is public, so auth is per endpoint here."""

from fastapi import APIRouter, status

from team_notes_api.api.deps import CurrentUser
from team_notes_api.core.db import SessionDep
from team_notes_api.schemas.common import Envelope, error_responses
from team_notes_api.schemas.users import UserCreate, UserCreated, UserOut
from team_notes_api.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Register a user and receive a bearer token",
    responses=error_responses(409, 422, s409="Email already registered (`conflict`)."),
)
def create_user(payload: UserCreate, session: SessionDep) -> Envelope[UserCreated]:
    """Create a user. The email is case-normalized and must be unique.

    The returned `token` is shown **only once**; send it as `Authorization: Bearer <token>`.
    """
    user, token = user_service.create_user(session, payload.email, payload.display_name)
    return Envelope(data=UserCreated(user=UserOut.model_validate(user), token=token))


@router.get(
    "/me",
    summary="Get the authenticated user",
    responses=error_responses(401),
)
def get_me(user: CurrentUser) -> Envelope[UserOut]:
    """Return the user identified by the bearer token."""
    return Envelope(data=UserOut.model_validate(user))

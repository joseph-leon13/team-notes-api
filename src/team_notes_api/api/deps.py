"""Request dependencies: the authenticated caller and pagination parameters.

``CurrentUser`` is the single seam for authentication. Swapping the stand-in bearer
tokens for real auth (OIDC, sessions, ...) means changing only :func:`get_current_user`.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from team_notes_api.core.db import SessionDep
from team_notes_api.core.errors import UnauthenticatedError
from team_notes_api.models import User
from team_notes_api.services.users import get_user_by_token

_bearer = HTTPBearer(auto_error=False, description="Token returned once by POST /api/v1/users.")


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Resolve ``Authorization: Bearer <token>`` to a user, or raise 401."""
    if credentials is None or not credentials.credentials:
        raise UnauthenticatedError()
    user = get_user_by_token(session, credentials.credentials)
    if user is None:
        raise UnauthenticatedError("The bearer token is invalid.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass(frozen=True)
class Page:
    """Validated pagination parameters."""

    limit: int
    cursor: str | None


def get_page_params(
    request: Request,
    limit: Annotated[int | None, Query(ge=1, le=100, description="Page size (default 20).")] = None,
    cursor: Annotated[
        str | None, Query(max_length=512, description="`meta.next_cursor` of the previous page.")
    ] = None,
) -> Page:
    """Parse ``limit``/``cursor``; the default size and cap come from settings."""
    settings = request.app.state.settings
    size = settings.default_page_size if limit is None else min(limit, settings.max_page_size)
    return Page(limit=size, cursor=cursor)


PageParams = Annotated[Page, Depends(get_page_params)]

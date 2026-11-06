"""Request and response schemas for users."""

from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    StringConstraints,
)

from team_notes_api.schemas.common import RequestModel, UTCTimestamp

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def _strip(value: object) -> object:
    """Trim surrounding whitespace before email validation (inner spaces stay invalid)."""
    return value.strip() if isinstance(value, str) else value


NormalizedEmail = Annotated[EmailStr, BeforeValidator(_strip), AfterValidator(str.lower)]
"""An address validated by ``email-validator`` (syntax only, no DNS/deliverability
lookups), then lower-cased whole so uniqueness is case-insensitive."""


class UserCreate(RequestModel):
    """Body of ``POST /users``."""

    email: NormalizedEmail
    display_name: DisplayName


class UserOut(BaseModel):
    """Public view of a user. Never includes the token hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    created_at: UTCTimestamp


class UserCreated(BaseModel):
    """Response of ``POST /users``: the user and their bearer token, shown only once."""

    user: UserOut
    token: str

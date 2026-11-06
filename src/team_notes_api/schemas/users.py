"""Request and response schemas for users."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from team_notes_api.schemas.common import RequestModel, UTCTimestamp

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
EmailStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)]


def normalize_email(value: str) -> str:
    """Lower-case and strip an email, rejecting values without a plausible ``local@domain``.

    This is a shape check, not RFC 5322 validation; deliverability is out of scope.
    """
    email = value.strip().lower()
    local, sep, domain = email.partition("@")
    if not sep or not local or "." not in domain or any(c.isspace() for c in email):
        raise ValueError("must be an email address like name@example.com")
    return email


class UserCreate(RequestModel):
    """Body of ``POST /users``."""

    email: EmailStr
    display_name: DisplayName

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return normalize_email(value)


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

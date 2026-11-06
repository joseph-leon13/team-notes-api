"""Request and response schemas for teams and memberships."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from team_notes_api.core.roles import Role
from team_notes_api.schemas.common import RequestModel, UTCTimestamp
from team_notes_api.schemas.users import EmailStr, normalize_email

TeamName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class TeamCreate(RequestModel):
    """Body of ``POST /teams``."""

    name: TeamName


class MemberAdd(RequestModel):
    """Body of ``POST /teams/{team_id}/members``: an existing user's email and a role."""

    email: EmailStr
    role: Role = Role.MEMBER

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return normalize_email(value)


class TeamOut(BaseModel):
    """A team as seen by one of its members; ``role`` is the caller's role."""

    id: int
    name: str
    created_at: UTCTimestamp
    role: Role


class MemberOut(BaseModel):
    """One member of a team."""

    user_id: int
    email: str
    display_name: str
    role: Role
    joined_at: UTCTimestamp


class TeamDetail(TeamOut):
    """A team together with its members."""

    members: list[MemberOut]

"""Team and membership endpoints. Every endpoint requires a bearer token."""

from fastapi import APIRouter, Response, status

from team_notes_api.api.deps import CurrentUser
from team_notes_api.core.db import SessionDep
from team_notes_api.models import Membership
from team_notes_api.schemas.common import Envelope, error_responses
from team_notes_api.schemas.teams import MemberAdd, MemberOut, TeamCreate, TeamDetail, TeamOut
from team_notes_api.services import teams as team_service

router = APIRouter(prefix="/teams", tags=["teams"])


def _team_out(membership: Membership) -> TeamOut:
    """Render a team from the caller's membership."""
    team = membership.team
    return TeamOut(id=team.id, name=team.name, created_at=team.created_at, role=membership.role)


def _member_out(membership: Membership) -> MemberOut:
    """Render one membership with its user's details."""
    return MemberOut(
        user_id=membership.user_id,
        email=membership.user.email,
        display_name=membership.user.display_name,
        role=membership.role,
        joined_at=membership.created_at,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a team",
    responses=error_responses(401, 422),
)
def create_team(payload: TeamCreate, session: SessionDep, user: CurrentUser) -> Envelope[TeamOut]:
    """Create a team. The caller becomes its first owner."""
    membership = team_service.create_team(session, user, payload.name)
    return Envelope(data=_team_out(membership))


@router.get("", summary="List my teams", responses=error_responses(401))
def list_teams(session: SessionDep, user: CurrentUser) -> Envelope[list[TeamOut]]:
    """List the teams the caller belongs to, with the caller's role in each."""
    memberships = team_service.list_memberships(session, user)
    return Envelope(data=[_team_out(membership) for membership in memberships])


@router.get(
    "/{team_id}",
    summary="Get a team and its members",
    responses=error_responses(401, 404, 422),
)
def get_team(team_id: int, session: SessionDep, user: CurrentUser) -> Envelope[TeamDetail]:
    """Return the team and its members. Non-members get 404, never a hint it exists."""
    membership, members = team_service.get_team_with_members(session, team_id, user)
    detail = TeamDetail(
        **_team_out(membership).model_dump(), members=[_member_out(m) for m in members]
    )
    return Envelope(data=detail)


@router.post(
    "/{team_id}/members",
    status_code=status.HTTP_201_CREATED,
    summary="Add a member (owner only)",
    responses=error_responses(
        401,
        403,
        404,
        409,
        422,
        s403="Caller is a member but not an owner (`forbidden`).",
        s404="Team not visible to caller, or no user has this email (`not_found`).",
        s409="User is already a member (`conflict`).",
    ),
)
def add_member(
    team_id: int, payload: MemberAdd, session: SessionDep, user: CurrentUser
) -> Envelope[MemberOut]:
    """Add an existing user, by email, to the team with the given role (default `member`)."""
    membership = team_service.add_member(session, team_id, user, payload.email, payload.role)
    return Envelope(data=_member_out(membership))


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remove a member or leave the team",
    responses=error_responses(
        401,
        403,
        404,
        409,
        422,
        s403="A member tried to remove someone other than themselves (`forbidden`).",
        s409="This would remove the team's last owner (`last_owner`).",
    ),
)
def remove_member(team_id: int, user_id: int, session: SessionDep, user: CurrentUser) -> Response:
    """Remove a member. Owners may remove anyone; members may only remove themselves.

    The last owner cannot be removed (409 `last_owner`).
    """
    team_service.remove_member(session, team_id, user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

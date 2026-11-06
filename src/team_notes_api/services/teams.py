"""Teams and memberships: creation, membership lookup, adding and removing members.

:func:`get_membership_or_404` is the authorization chokepoint for team endpoints: it
resolves the caller's membership with one query, and "no membership" is reported
exactly like "no team" (404) so team existence never leaks to outsiders.
"""

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload

from team_notes_api.core.errors import ConflictError, ForbiddenError, LastOwnerError, NotFoundError
from team_notes_api.core.roles import Role
from team_notes_api.models import Membership, Team, User
from team_notes_api.services import policy
from team_notes_api.services.users import get_user_by_email


def get_membership_or_404(session: Session, team_id: int, user: User) -> Membership:
    """Return ``user``'s membership in the team (with the team loaded), or raise 404."""
    membership = session.scalar(
        select(Membership)
        .where(Membership.team_id == team_id, Membership.user_id == user.id)
        .options(joinedload(Membership.team))
    )
    if membership is None:
        raise NotFoundError("Team not found.")
    return membership


def create_team(session: Session, user: User, name: str) -> Membership:
    """Create a team with ``user`` as its owner; return the owner membership."""
    team = Team(name=name)
    membership = Membership(team=team, user=user, role=Role.OWNER.value)
    session.add_all([team, membership])
    session.commit()
    return membership


def list_memberships(session: Session, user: User) -> list[Membership]:
    """Return the caller's memberships (teams loaded), oldest team first."""
    return list(
        session.scalars(
            select(Membership)
            .where(Membership.user_id == user.id)
            .options(joinedload(Membership.team))
            .order_by(Membership.team_id)
        )
    )


def get_team_with_members(
    session: Session, team_id: int, user: User
) -> tuple[Membership, list[Membership]]:
    """Return the caller's membership and every membership of the team (users loaded)."""
    membership = get_membership_or_404(session, team_id, user)
    if not policy.can_view_team(membership.role):
        raise ForbiddenError()
    members = session.scalars(
        select(Membership)
        .where(Membership.team_id == team_id)
        .options(joinedload(Membership.user))
        .order_by(Membership.id)
    )
    return membership, list(members)


def add_member(session: Session, team_id: int, actor: User, email: str, role: Role) -> Membership:
    """Add the user with ``email`` to the team. Owner only.

    Raises 404 for an unknown email and 409 if the user is already a member.
    """
    actor_membership = get_membership_or_404(session, team_id, actor)
    if not policy.can_manage_members(actor_membership.role):
        raise ForbiddenError("Only team owners can add members.")

    target = get_user_by_email(session, email)
    if target is None:
        raise NotFoundError("No user with this email.")

    membership = Membership(team_id=team_id, user=target, role=role.value)
    session.add(membership)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("This user is already a member of the team.") from exc
    return membership


def remove_member(session: Session, team_id: int, actor: User, user_id: int) -> None:
    """Remove ``user_id`` from the team. Owners remove anyone; members only themselves.

    The last-owner guard is part of the DELETE statement itself (delete only if the
    target is not an owner, or another owner remains), so two owners removing each
    other concurrently cannot leave the team ownerless.
    """
    actor_membership = get_membership_or_404(session, team_id, actor)
    if not policy.can_remove_member(actor_membership.role, actor.id, user_id):
        raise ForbiddenError("Members can only remove themselves.")

    target = session.scalar(
        select(Membership).where(Membership.team_id == team_id, Membership.user_id == user_id)
    )
    if target is None:
        raise NotFoundError("Member not found.")

    other = aliased(Membership)
    other_owners = (
        select(func.count())
        .select_from(other)
        .where(other.team_id == team_id, other.role == Role.OWNER.value, other.id != target.id)
        .scalar_subquery()
    )
    result = session.execute(
        delete(Membership).where(
            Membership.id == target.id,
            or_(Membership.role != Role.OWNER.value, other_owners > 0),
        )
    )
    if result.rowcount != 1:
        session.rollback()
        raise LastOwnerError()
    session.commit()

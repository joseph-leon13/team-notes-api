"""Pure role rules: who may do what inside a team.

These functions take plain values (a role, user ids) and return a bool. They do no
I/O, which keeps every permission decision in one readable, exhaustively testable
place. Membership itself (is the caller in the team at all?) is NOT decided here: the
services resolve it with a JOIN, and a non-member gets 404 before policy is consulted.
"""

from team_notes_api.core.roles import Role


def can_view_team(role: Role | str) -> bool:
    """Any member may see the team and its member list."""
    return role in (Role.OWNER, Role.MEMBER)


def can_read_note(role: Role | str) -> bool:
    """Any member may read the team's notes."""
    return role in (Role.OWNER, Role.MEMBER)


def can_create_note(role: Role | str) -> bool:
    """Any member may create notes in the team."""
    return role in (Role.OWNER, Role.MEMBER)


def can_edit_note(role: Role | str) -> bool:
    """Any member may edit any note in the team (concurrency is handled by versioning)."""
    return role in (Role.OWNER, Role.MEMBER)


def can_delete_note(role: Role | str, actor_id: int, creator_id: int) -> bool:
    """A note may be deleted by its creator or by a team owner."""
    return role == Role.OWNER or (role == Role.MEMBER and actor_id == creator_id)


def can_manage_members(role: Role | str) -> bool:
    """Only owners may add members."""
    return role == Role.OWNER


def can_remove_member(role: Role | str, actor_id: int, target_id: int) -> bool:
    """Owners may remove anyone; a member may remove only themselves (leave the team).

    The last-owner guard is a state check, enforced atomically by the service.
    """
    return role == Role.OWNER or (role == Role.MEMBER and actor_id == target_id)

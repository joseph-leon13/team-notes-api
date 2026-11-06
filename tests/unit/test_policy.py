"""Truth tables for the pure role rules in ``policy.py``."""

import pytest

from team_notes_api.core.roles import Role
from team_notes_api.services import policy

ME, OTHER = 1, 2


@pytest.mark.parametrize(
    "rule",
    [policy.can_view_team, policy.can_read_note, policy.can_create_note, policy.can_edit_note],
)
@pytest.mark.parametrize(
    ("role", "allowed"), [(Role.OWNER, True), (Role.MEMBER, True), ("stranger", False)]
)
def test_any_member_may_view_read_create_and_edit(rule, role, allowed):
    assert rule(role) is allowed


@pytest.mark.parametrize(
    ("role", "allowed"), [(Role.OWNER, True), (Role.MEMBER, False), ("stranger", False)]
)
def test_only_owners_manage_members(role, allowed):
    assert policy.can_manage_members(role) is allowed


@pytest.mark.parametrize(
    ("role", "creator_id", "allowed"),
    [
        (Role.OWNER, ME, True),
        (Role.OWNER, OTHER, True),
        (Role.MEMBER, ME, True),
        (Role.MEMBER, OTHER, False),
        ("stranger", ME, False),
    ],
)
def test_delete_note_needs_creator_or_owner(role, creator_id, allowed):
    assert policy.can_delete_note(role, actor_id=ME, creator_id=creator_id) is allowed


@pytest.mark.parametrize(
    ("role", "target_id", "allowed"),
    [
        (Role.OWNER, ME, True),
        (Role.OWNER, OTHER, True),
        (Role.MEMBER, ME, True),
        (Role.MEMBER, OTHER, False),
        ("stranger", ME, False),
    ],
)
def test_remove_member_needs_owner_or_self(role, target_id, allowed):
    assert policy.can_remove_member(role, actor_id=ME, target_id=target_id) is allowed


def test_policy_accepts_raw_role_strings_from_the_database():
    assert policy.can_manage_members("owner") is True
    assert policy.can_manage_members("member") is False

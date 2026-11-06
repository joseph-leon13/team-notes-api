"""The ``Role`` vocabulary, shared by models, policy and schemas without coupling them."""

from enum import StrEnum


class Role(StrEnum):
    """A member's role inside one team."""

    OWNER = "owner"
    MEMBER = "member"

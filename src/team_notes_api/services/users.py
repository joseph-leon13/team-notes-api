"""User registration and token-based lookup."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from team_notes_api.core.errors import ConflictError
from team_notes_api.core.security import generate_token, hash_token
from team_notes_api.models import User


def create_user(session: Session, email: str, display_name: str) -> tuple[User, str]:
    """Create a user and return it with its plaintext token (the only time it exists).

    ``email`` must already be normalized. A duplicate raises :class:`ConflictError`;
    the unique constraint is the real guard, the pre-check only gives a clean message.
    """
    if session.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError("A user with this email already exists.")

    token = generate_token()
    user = User(email=email, display_name=display_name, token_hash=hash_token(token))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("A user with this email already exists.") from exc
    return user, token


def get_user_by_token(session: Session, token: str) -> User | None:
    """Return the user whose token digest matches ``token``, or ``None``."""
    return session.scalar(select(User).where(User.token_hash == hash_token(token)))


def get_user_by_email(session: Session, email: str) -> User | None:
    """Return the user with this (normalized) email, or ``None``."""
    return session.scalar(select(User).where(User.email == email))

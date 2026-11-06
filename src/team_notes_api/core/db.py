"""Database engine, session factory and the request-scoped session dependency."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""


def build_engine(database_url: str) -> Engine:
    """Create an engine, applying SQLite pragmas when the URL targets SQLite.

    SQLite ships with foreign-key enforcement OFF per connection, so ``ON DELETE
    CASCADE`` would silently do nothing without the pragma below.
    """
    engine = create_engine(database_url)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to ``engine`` (objects stay usable after commit)."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    """Yield one database session per request, from the factory stored on the app.

    Commits happen explicitly in the service layer, never here: since FastAPI 0.118
    dependency teardown runs after the response is sent, so a commit failing in
    teardown could no longer change the status the client already received.
    """
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]

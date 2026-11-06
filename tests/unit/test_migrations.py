"""The Alembic migrations build exactly the schema the models declare, and round-trip.

``conftest`` builds test databases with ``create_all`` for speed; this module is what
keeps that shortcut honest. If a model changes without a migration (or vice versa),
the drift test fails.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from team_notes_api import models  # noqa: F401  (registers tables on Base.metadata)
from team_notes_api.core.db import Base

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_TABLES = {"users", "teams", "memberships", "notes", "note_tags"}


@pytest.fixture
def migration_db(tmp_path, monkeypatch):
    """An empty temp SQLite file that ``migrations/env.py`` targets via the settings env."""
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setenv("NOTES_DATABASE_URL", url)
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.attributes["configure_logging"] = False  # keep pytest's logging intact
    engine = create_engine(url)
    yield config, engine
    engine.dispose()


def _tables(engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_head_matches_the_models_with_no_drift(migration_db):
    config, engine = migration_db

    command.upgrade(config, "head")

    with engine.connect() as connection:
        drift = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert drift == []
    assert _tables(engine) == APP_TABLES


def test_migrated_schema_keeps_the_load_bearing_constraints(migration_db):
    config, engine = migration_db

    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert {fk["options"].get("ondelete") for fk in inspector.get_foreign_keys("note_tags")} == {
        "CASCADE"
    }
    assert inspector.get_pk_constraint("note_tags")["constrained_columns"] == ["note_id", "tag"]
    assert [c["name"] for c in inspector.get_check_constraints("memberships")] == [
        "ck_memberships_role"
    ]
    indexes = {ix["name"]: ix for ix in inspector.get_indexes("notes")}
    assert indexes["ix_notes_team_updated_id"]["column_names"] == ["team_id", "updated_at", "id"]
    user_indexes = {ix["name"]: ix for ix in inspector.get_indexes("users")}
    assert user_indexes["ix_users_token_hash"]["unique"]


def test_downgrade_base_then_upgrade_head_round_trips(migration_db):
    config, engine = migration_db
    command.upgrade(config, "head")

    command.downgrade(config, "base")
    assert _tables(engine) == set()

    command.upgrade(config, "head")
    with engine.connect() as connection:
        drift = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert drift == []
    assert _tables(engine) == APP_TABLES

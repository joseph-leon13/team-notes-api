"""Shared fixtures: every test gets a fresh app backed by its own temporary SQLite file.

A temp *file* (not ``:memory:``) is used on purpose: SQLite's in-memory databases are
per-connection, and FastAPI's TestClient may serve requests from other threads, which
would then see an empty database.
"""

import pytest
from fastapi.testclient import TestClient

from team_notes_api.config import Settings
from team_notes_api.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(create_app(settings)) as test_client:
        yield test_client

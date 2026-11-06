"""Application factory: wires settings, database, routers and error handlers.

Run with ``uvicorn team_notes_api.main:create_app --factory`` so that importing this
module never touches the database.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from team_notes_api import models  # noqa: F401  (registers tables on Base.metadata)
from team_notes_api.api import v1 as api_v1
from team_notes_api.core.config import Settings, get_settings
from team_notes_api.core.db import Base, SessionDep, build_engine, build_session_factory
from team_notes_api.core.errors import register_error_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a configured FastAPI application.

    Tables are created on startup (``create_all``); a production deployment would use
    migrations instead (see README, "What I'd change").
    """
    settings = settings or get_settings()
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)

    app = FastAPI(
        title="Team Notes API",
        version="0.1.0",
        description="Capture and work with notes shared inside small teams.",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    register_error_handlers(app)
    if settings.cors_origin_list:
        # Explicit origins only (never "*"); bearer tokens travel in a header, so no
        # cookies/credentials are needed for cross-origin calls.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            expose_headers=["Location"],
        )
    app.include_router(api_v1.router)

    @app.get("/health", tags=["health"], summary="Liveness and database check")
    def health(session: SessionDep) -> dict[str, str]:
        """Return ``ok`` when the service is up and the database answers a trivial query."""
        session.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app

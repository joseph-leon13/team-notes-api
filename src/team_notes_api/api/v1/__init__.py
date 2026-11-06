"""Version 1 of the HTTP API: one router per area, aggregated under ``/api/v1``."""

from fastapi import APIRouter

from team_notes_api.api.v1 import notes, teams, users

router = APIRouter(prefix="/api/v1")
router.include_router(users.router)
router.include_router(teams.router)
router.include_router(notes.team_notes_router)
router.include_router(notes.router)

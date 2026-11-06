"""Version 1 of the HTTP API: one router per area, aggregated under ``/api/v1``."""

from fastapi import APIRouter

from team_notes_api.api.v1 import users

router = APIRouter(prefix="/api/v1")
router.include_router(users.router)

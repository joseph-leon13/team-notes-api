"""The ``/api/v1`` router: aggregates every area router under one versioned prefix."""

from fastapi import APIRouter

from team_notes_api.api.routers import users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(users.router)

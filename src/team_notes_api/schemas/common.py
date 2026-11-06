"""Shared response schemas: the success and error envelopes and the page metadata."""

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


def _format_utc(value: datetime) -> str:
    """Serialize a datetime as UTC ISO-8601 with microseconds and a ``Z`` suffix."""
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


UTCTimestamp = Annotated[datetime, PlainSerializer(_format_utc, return_type=str, when_used="json")]
"""A datetime that is always rendered as ``YYYY-MM-DDTHH:MM:SS.ffffffZ`` in JSON."""


class RequestModel(BaseModel):
    """Base for request bodies: unknown fields are rejected, not silently dropped."""

    model_config = ConfigDict(extra="forbid")


class Envelope[DataT](BaseModel):
    """Success envelope: ``{"data": ..., "meta": {...}}``."""

    data: DataT
    meta: dict[str, Any] = Field(default_factory=dict)


class PageMeta(BaseModel):
    """Keyset pagination metadata. ``next_cursor`` is null on the last page."""

    limit: int
    next_cursor: str | None
    has_more: bool


class PageEnvelope[ItemT](BaseModel):
    """Success envelope for a page of items."""

    data: list[ItemT]
    meta: PageMeta


class ErrorBody(BaseModel):
    """The inner error object."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Error envelope: ``{"error": {"code", "message", "details"}}``."""

    error: ErrorBody


_ERROR_DESCRIPTIONS: dict[int, str] = {
    401: "Missing or invalid bearer token (`unauthenticated`).",
    403: "Your role in the team does not allow this (`forbidden`).",
    404: "Not found, or not visible to you (`not_found`).",
    409: "Conflicts with current state.",
    422: "Invalid request (`validation_error`).",
}


def error_responses(*statuses: int, **overrides: str) -> dict[int | str, dict[str, Any]]:
    """Build an OpenAPI ``responses`` mapping documenting the given error statuses.

    ``overrides`` replace a status's description, keyed as ``s409="..."``.
    """
    responses: dict[int | str, dict[str, Any]] = {}
    for status in statuses:
        description = overrides.get(f"s{status}", _ERROR_DESCRIPTIONS[status])
        responses[status] = {"model": ErrorEnvelope, "description": description}
    return responses

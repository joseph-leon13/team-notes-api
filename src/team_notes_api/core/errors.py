"""Typed application errors, the error envelope, and the global exception handlers.

Every non-2xx response leaves the service as ``{"error": {"code", "message", "details"}}``.
Services raise :class:`AppError` subclasses; the handlers registered by
:func:`register_error_handlers` translate them (and framework errors: unknown routes,
405s, request validation, unexpected exceptions) into that one shape.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for errors that map to a specific HTTP status and error code."""

    status_code: int = 400
    code: str = "bad_request"
    message: str = "Bad request."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        self.headers = headers
        super().__init__(self.message)


class UnauthenticatedError(AppError):
    """The request carries no valid bearer token (401)."""

    status_code = 401
    code = "unauthenticated"
    message = "A valid bearer token is required."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, headers={"WWW-Authenticate": "Bearer"})


class ForbiddenError(AppError):
    """The caller is a team member but their role does not allow the action (403)."""

    status_code = 403
    code = "forbidden"
    message = "Your role does not allow this action."


class NotFoundError(AppError):
    """The resource does not exist or is not visible to the caller (404)."""

    status_code = 404
    code = "not_found"
    message = "Resource not found."


class ConflictError(AppError):
    """The request conflicts with existing state, e.g. a duplicate (409)."""

    status_code = 409
    code = "conflict"
    message = "The resource already exists."


class LastOwnerError(AppError):
    """Removing this membership would leave the team without an owner (409)."""

    status_code = 409
    code = "last_owner"
    message = "A team must keep at least one owner."


class VersionConflictError(AppError):
    """The client edited a stale version of a note (409)."""

    status_code = 409
    code = "version_conflict"
    message = "The note was modified by someone else; reload and retry."

    def __init__(self, current_version: int) -> None:
        super().__init__(details={"current_version": current_version})


class InvalidCursorError(AppError):
    """The pagination cursor could not be decoded (422)."""

    status_code = 422
    code = "invalid_cursor"
    message = "The pagination cursor is malformed."


_HTTP_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
}


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the JSON body of the error envelope."""
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    """Render a typed application error."""
    return JSONResponse(
        error_body(exc.code, exc.message, exc.details),
        status_code=exc.status_code,
        headers=exc.headers,
    )


def _handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Render framework HTTP errors (unknown route, 405, ...) in the envelope."""
    code = _HTTP_STATUS_CODES.get(exc.status_code, "http_error")
    return JSONResponse(
        error_body(code, str(exc.detail)),
        status_code=exc.status_code,
        headers=exc.headers,
    )


def _handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Render request validation failures as 422 ``validation_error``.

    Only ``loc``/``msg``/``type`` are copied: pydantic's ``ctx`` may hold exception
    objects that are not JSON-serializable, and ``input`` would echo the request back.
    """
    errors = [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        error_body("validation_error", "The request is invalid.", {"errors": errors}),
        status_code=422,
    )


def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log an unexpected exception and return a generic 500 without leaking a trace."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        error_body("internal_error", "An unexpected error occurred."),
        status_code=500,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Install every global exception handler on ``app``."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)

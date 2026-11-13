"""Mapping domain errors to the contract's error shape.

Every non-2xx response has the body `{"error": {"code", "message"}}`
(`docs/web-api.md`). Routes never build that by hand: they raise domain
errors from `jobpilot.errors` (or let FastAPI raise its own), and the
handlers installed here translate them in one place. That keeps status
codes and codes consistent and keeps internals (table names, stack
traces) out of responses.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from jobpilot import errors
from jobpilot.logging import get_logger

logger = get_logger(__name__)

#: (exception type, HTTP status, contract code). First match wins, so more
#: specific types must come before their base classes.
ERROR_TABLE: list[tuple[type[Exception], int, str]] = [
    (errors.TooManyAttemptsError, 429, "rate_limited"),
    (errors.AuthError, 401, "unauthorized"),
    (errors.RecordNotFoundError, 404, "not_found"),
    (errors.UnsupportedFileTypeError, 415, "unsupported_file_type"),
    (errors.FileTooLargeError, 413, "file_too_large"),
    (errors.ResumeNotReadyError, 409, "resume_not_ready"),
    # The contract has no "conflict" code; an export or decision against
    # a tailoring that is not ready is a request the server cannot honour
    # yet, which `validation_failed` describes closest.
    (errors.TailoringNotReadyError, 409, "validation_failed"),
    (errors.RequestRejectedError, 422, "validation_failed"),
    (errors.ValidationError, 422, "validation_failed"),
]

_STATUS_CODES = {
    401: "unauthorized",
    403: "unauthorized",
    404: "not_found",
    429: "rate_limited",
}

#: Messages safe to show even when the underlying error text is not.
_FIXED_MESSAGES = {
    "not_found": "not found",
    "internal": "internal error",
}


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _response(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(error_body(code, message), status_code=status, headers=headers)


def classify(exc: Exception) -> tuple[int, str, str]:
    """Return `(status, code, message)` for a domain exception."""

    for exc_type, status, code in ERROR_TABLE:
        if isinstance(exc, exc_type):
            return status, code, _FIXED_MESSAGES.get(code, str(exc))
    return 500, "internal", _FIXED_MESSAGES["internal"]


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(errors.JobPilotError)
    async def handle_domain_error(request: Request, exc: errors.JobPilotError) -> JSONResponse:
        status, code, message = classify(exc)
        if status >= 500:
            logger.error("unhandled_domain_error", error=str(exc), path=request.url.path)
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
        return _response(status, code, message, headers)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code)
        if code is None:
            code = "internal" if exc.status_code >= 500 else "validation_failed"
        message = _FIXED_MESSAGES.get(code, str(exc.detail))
        return _response(exc.status_code, code, message, getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        detail = first.get("msg", "invalid request")
        message = f"{location}: {detail}" if location else detail
        return _response(422, "validation_failed", message)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", path=request.url.path)
        return _response(500, "internal", _FIXED_MESSAGES["internal"])

"""One error shape for the whole API: ErrorOut. Never a stack trace, never input values.

Call ``install_error_handlers(app)`` once when building the app.
"""

from __future__ import annotations

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class ErrorOut(BaseModel):
    error: str  # stable machine code, e.g. "unauthorized", "email_taken"
    message: str  # short human text; never contains submitted values
    fields: list[str] | None = None  # for validation errors: which inputs were wrong


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        error: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status, self.error, self.message, self.headers = status, error, message, headers


def unauthorized(message: str = "not authenticated") -> ApiError:
    return ApiError(401, "unauthorized", message, headers={"WWW-Authenticate": "Bearer"})


# Responses block for route decorators so OpenAPI documents the error shape.
ERROR_RESPONSES: dict[int | str, dict] = {
    code: {"model": ErrorOut} for code in (400, 401, 404, 409, 422, 429, 500)
}


def _json(status: int, body: ErrorOut, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(body.model_dump(exclude_none=True), status_code=status, headers=headers)


def _code_for(status: int) -> str:
    try:
        return HTTPStatus(status).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "error"


async def _api_error(_req: Request, exc: ApiError) -> JSONResponse:
    return _json(exc.status, ErrorOut(error=exc.error, message=exc.message), exc.headers)


async def _http_error(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
    msg = exc.detail if isinstance(exc.detail, str) else _code_for(exc.status_code)
    return _json(
        exc.status_code,
        ErrorOut(error=_code_for(exc.status_code), message=msg),
        getattr(exc, "headers", None),
    )


async def _validation_error(_req: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic's own detail echoes the submitted input (passwords included): report locations only.
    fields = sorted(
        {".".join(str(p) for p in e.get("loc", ()) if p != "body") or "body" for e in exc.errors()}
    )
    return _json(422, ErrorOut(error="validation_error", message="invalid request", fields=fields))


async def _unhandled(req: Request, exc: Exception) -> JSONResponse:
    # Exception text can carry SQL parameters or user data, so log only the type and route.
    log.error("unhandled %s on %s %s", type(exc).__name__, req.method, req.url.path)
    return _json(500, ErrorOut(error="internal_error", message="internal server error"))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)

"""POST /api/v1/ingest/estimates: device-side estimates (INJ-1). Thin: see services.injection."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES, ApiError
from backend.services import injection as svc

router = APIRouter(prefix="/api/v1", tags=["ingest"])


class InjectionResult(BaseModel):
    run_id: str
    session_id: str
    batch_sha256: str
    windows: int
    hearts: int
    motion: int
    code_version: str
    duplicate: bool


@router.post(
    "/ingest/estimates",
    response_model=InjectionResult,
    status_code=201,
    responses={
        200: {"model": InjectionResult, "description": "Replay: already stored"},
        **ERROR_RESPONSES,
    },
)
def ingest_estimates(
    body: dict[str, Any],
    user_id: CurrentUser,
    db: DbSession,
    response: Response,
    x_code_version: Annotated[str | None, Header()] = None,
):
    """Store one batch of WindowEstimate, experimental HeartEstimate and motion values
    for a session. Idempotent by batch sha256; all or nothing."""
    try:
        out = svc.inject(db, user_id, body, x_code_version)
    except svc.InjectionError as exc:
        status = 404 if str(exc) == svc.SESSION_NOT_FOUND else 422
        raise ApiError(status, "invalid_batch", "; ".join([str(exc), *exc.errors])[:2000]) from None
    if out["duplicate"]:
        response.status_code = 200
    return out

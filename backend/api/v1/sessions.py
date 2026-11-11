"""Recording sessions: register from the inbox, list, get, windows. Thin: see services."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES, ApiError
from backend.schemas.contracts import SessionRecord, WindowEstimate
from backend.services import sessions as svc

router = APIRouter(prefix="/api/v1", tags=["sessions"])


class SessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    src_dir: str = Field(
        min_length=1, max_length=512, description="Folder name relative to DATA_DIR/inbox"
    )


def _not_found(what: str) -> ApiError:
    return ApiError(404, "not_found", f"{what} not found")


@router.post(
    "/sessions",
    response_model=SessionRecord,
    status_code=201,
    responses={200: {"model": SessionRecord, "description": "Already ingested"}, **ERROR_RESPONSES},
)
def register_session(body: SessionIn, user_id: CurrentUser, db: DbSession, response: Response):
    try:
        rec, created = svc.register_session(db, user_id, body.src_dir)
    except svc.InboxPathError as exc:
        raise ApiError(400, "bad_src_dir", str(exc)) from None
    except svc.IngestError as exc:
        raise ApiError(400, "ingest_failed", str(exc)) from None
    if not created:
        response.status_code = 200
    return rec


@router.get("/sessions", response_model=list[SessionRecord], responses=ERROR_RESPONSES)
def list_sessions(
    user_id: CurrentUser,
    db: DbSession,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=svc.MAX_LIMIT)] = 100,
):
    try:
        return svc.list_sessions(db, user_id, start, end, limit)
    except ValueError as exc:
        raise ApiError(400, "bad_range", str(exc)) from None


@router.get("/sessions/{session_id}", response_model=SessionRecord, responses=ERROR_RESPONSES)
def get_session(session_id: str, user_id: CurrentUser, db: DbSession):
    rec = svc.get_session(db, user_id, session_id)
    if rec is None:
        raise _not_found("session")
    return rec


@router.get("/windows", response_model=list[WindowEstimate], responses=ERROR_RESPONSES)
def list_windows(session_id: Annotated[str, Query(min_length=1)], user_id: CurrentUser,
                 db: DbSession):  # fmt: skip
    rows = svc.list_windows(db, user_id, session_id)
    if rows is None:
        raise _not_found("session")
    return rows

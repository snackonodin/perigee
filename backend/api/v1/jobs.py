"""Processing jobs: submit a run for the background worker, poll its status. Thin."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES, ApiError
from backend.schemas.contracts import RunRecord, RunStatus
from backend.services import jobs as svc

router = APIRouter(prefix="/api/v1", tags=["jobs"])


class JobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)


class JobCreated(BaseModel):
    id: str
    status: RunStatus


class JobOut(BaseModel):
    """No log or params: logs can hold exception text; params are the caller's own input."""

    id: str
    kind: str
    status: RunStatus
    code_version: str
    started: datetime | None = None
    finished: datetime | None = None


def _out(rec: RunRecord) -> JobOut:
    return JobOut(
        id=rec.id, kind=rec.kind, status=rec.status, code_version=rec.code_version,
        started=rec.started, finished=rec.finished,
    )  # fmt: skip


@router.post("/jobs/process", response_model=JobCreated, status_code=202,
             responses=ERROR_RESPONSES)  # fmt: skip
def submit(body: JobIn, user_id: CurrentUser, db: DbSession) -> JobCreated:
    try:
        rec = svc.submit_job(db, user_id, body.kind, body.params)
    except svc.JobError as exc:
        raise ApiError(400, "bad_job", str(exc)) from None
    except svc.JobNotFound as exc:
        raise ApiError(404, "not_found", str(exc)) from None
    return JobCreated(id=rec.id, status=rec.status)


@router.get("/jobs/{job_id}", response_model=JobOut, responses=ERROR_RESPONSES)
def get(job_id: str, user_id: CurrentUser, db: DbSession) -> JobOut:
    try:
        return _out(svc.get_job(db, user_id, job_id))
    except svc.JobNotFound:
        raise ApiError(404, "not_found", "job not found") from None

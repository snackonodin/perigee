"""User-submitted processing jobs (pipeline runs owned by a user).

Only whitelisted kinds can be submitted, with whitelisted params. user_id always
comes from the caller (the token), never from params. Runs are executed by
backend.worker.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import CaptureSession, PipelineRun, RawFile, scoped
from backend.schemas.contracts import RunRecord
from backend.services import runs

# kind -> the params a user may set (user_id is added by the server)
ALLOWED: dict[str, frozenset[str]] = {
    "process_session": frozenset({"session_id"}),
    "run_nightly": frozenset({"date"}),
}


class JobError(ValueError):
    """Bad job request. Messages name fields, never values."""


class JobNotFound(LookupError):
    pass


def submit_job(db: Session, user_id: str, kind: str, params: dict[str, Any]) -> RunRecord:
    if kind not in ALLOWED:
        raise JobError(f"kind must be one of {sorted(ALLOWED)}")
    extra = set(params) - ALLOWED[kind]
    if extra:
        raise JobError(f"unexpected params: {sorted(extra)}")
    missing = ALLOWED[kind] - set(params)
    if missing:
        raise JobError(f"missing params: {sorted(missing)}")

    clean: dict[str, Any] = {"user_id": user_id}
    hashes: list[str] = []
    if kind == "process_session":
        sid = params["session_id"]
        owned = (
            isinstance(sid, str)
            and db.scalars(
                scoped(select(CaptureSession.id), CaptureSession, user_id).where(
                    CaptureSession.id == sid
                )
            ).one_or_none()
        )
        if not owned:
            raise JobNotFound("session not found")
        clean["session_id"] = sid
        hashes = list(
            db.scalars(
                scoped(select(RawFile.sha256), RawFile, user_id).where(RawFile.session_id == sid)
            )
        )
    else:
        try:
            clean["date"] = date.fromisoformat(str(params["date"])).isoformat()
        except ValueError:
            raise JobError("date must be YYYY-MM-DD") from None

    return runs.create_run(db, kind, clean, hashes, user_id=user_id)


def get_job(db: Session, user_id: str, run_id: str) -> RunRecord:
    row = db.scalars(
        scoped(select(PipelineRun), PipelineRun, user_id).where(PipelineRun.id == run_id)
    ).one_or_none()
    if row is None:
        raise JobNotFound("job not found")
    return runs.to_record(row)

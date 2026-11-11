"""Session queries and inbox registration for the sessions API. Every read is scoped()."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models import CaptureSession, WindowEstimateRow, scoped
from backend.schemas.contracts import SessionRecord, WindowEstimate
from backend.services.ingestion import IngestError, ingest_session, session_record

DEFAULT_RANGE = timedelta(days=30)
MAX_LIMIT = 500
_PART = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_MAX_DEPTH = 4


class InboxPathError(ValueError):
    """The requested inbox folder name is not acceptable (never echoes the input)."""


def inbox_root() -> Path:
    return get_settings().data_dir / "inbox"


def resolve_inbox_dir(name: str) -> Path:
    """Map a folder name relative to DATA_DIR/inbox to a real directory inside it.

    Rejects absolute paths, '..', backslashes, odd characters and symlinks that
    escape the inbox.
    """
    if not name or "\\" in name or name.startswith("/") or "\x00" in name:
        raise InboxPathError("src_dir must be a folder name relative to the inbox")
    parts = name.strip("/").split("/")
    if len(parts) > _MAX_DEPTH or any(p in (".", "..") or not _PART.match(p) for p in parts):
        raise InboxPathError("src_dir must be a folder name relative to the inbox")
    root = inbox_root().resolve()
    target = root.joinpath(*parts).resolve()
    if target == root or not target.is_relative_to(root):
        raise InboxPathError("src_dir must be a folder name relative to the inbox")
    if not target.is_dir():
        raise InboxPathError("no such folder in the inbox")
    return target


def register_session(db: Session, user_id: str, name: str) -> tuple[SessionRecord, bool]:
    """Ingest an inbox folder. Returns (record, created); created=False if already known."""
    src = resolve_inbox_dir(name)
    count = scoped(select(func.count()).select_from(CaptureSession), CaptureSession, user_id)
    before = db.scalar(count)
    rec = ingest_session(db, user_id, src)
    return rec, db.scalar(count) > before


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def list_sessions(
    db: Session,
    user_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 100,
) -> list[SessionRecord]:
    """Sessions whose start_utc is in [start, end); default: the last 30 days. Newest first."""
    end = _utc(end) if end else datetime.now(UTC)
    start = _utc(start) if start else end - DEFAULT_RANGE
    if start >= end:
        raise ValueError("from must be before to")
    stmt = (
        scoped(select(CaptureSession), CaptureSession, user_id)
        .where(CaptureSession.start_utc >= start, CaptureSession.start_utc < end)
        .order_by(CaptureSession.start_utc.desc())
        .limit(max(1, min(limit, MAX_LIMIT)))
    )
    return [session_record(db, s) for s in db.scalars(stmt)]


def _owned(db: Session, user_id: str, session_id: str) -> CaptureSession | None:
    return db.scalars(
        scoped(select(CaptureSession), CaptureSession, user_id).where(
            CaptureSession.id == session_id
        )
    ).one_or_none()


def get_session(db: Session, user_id: str, session_id: str) -> SessionRecord | None:
    s = _owned(db, user_id, session_id)
    return session_record(db, s) if s else None


def list_windows(db: Session, user_id: str, session_id: str) -> list[WindowEstimate] | None:
    """Window estimates of one of the user's sessions; None if the session is not theirs."""
    if _owned(db, user_id, session_id) is None:
        return None
    rows = db.scalars(
        scoped(select(WindowEstimateRow), WindowEstimateRow, user_id)
        .where(WindowEstimateRow.session_id == session_id)
        .order_by(WindowEstimateRow.t_start)
    )
    return [
        WindowEstimate(
            session_id=w.session_id,
            t_start=w.t_start,
            t_end=w.t_end,
            rr_a=w.rr_a,
            rr_b=w.rr_b,
            pnr_db=w.pnr_db,
            motion_flag=w.motion_flag,
            quality=w.quality,
            presence=w.presence,
            run_id=w.run_id,
        )  # fmt: skip
        for w in rows
    ]


__all__ = [
    "IngestError",
    "InboxPathError",
    "get_session",
    "inbox_root",
    "list_sessions",
    "list_windows",
    "register_session",
    "resolve_inbox_dir",
]

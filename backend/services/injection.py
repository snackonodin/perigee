"""INJ-1: ingest estimates computed on the capture device by the team scripts.

A batch carries one session's WindowEstimates, experimental HeartEstimates and
per-window motion values. ``inject`` is:

- validated first: nothing is written (not even a run) for a malformed batch;
- idempotent by batch sha256 (canonical JSON): a replay returns the earlier result;
- recorded as a run of kind "external_estimates" owned by the user, whose
  code_version is the client's (X-Code-Version) and whose input hash is the batch;
- all-or-nothing: session row, estimates and motion flags commit with the run's
  "succeeded" transition, or not at all.

The batch is archived read-only as DATA_DIR/raw/<session_id>/estimates-<sha>.json
(provenance; removed with the user by delete_user). A batch replaces earlier
estimates of the same session, like a re-run of process_session.

Motion values set motion_flag on the window with the same [t_start, t_end); their
score has no column yet and is kept only in the archived batch.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models import (
    CaptureSession,
    HeartEstimateRow,
    PipelineRun,
    User,
    WindowEstimateRow,
    scoped,
)
from backend.schemas.contracts import (
    AwareDatetime,
    HeartEstimate,
    Posture,
    RunStatus,
    SourceKind,
    WindowEstimate,
)
from backend.services import runs

KIND = "external_estimates"
CODE_VERSION_MAX = 64  # pipeline_runs.code_version column width
_NS = uuid.UUID("3b0c6f7e-5d1a-4c1e-9a77-2f8a1d6c4b10")  # session ids for new device sessions


class InjectionError(ValueError):
    """The batch cannot be accepted. Nothing was written."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SessionMeta(_Strict):
    """SessionRecord metadata for a session the server has not seen (no raw files)."""

    start_utc: AwareDatetime
    end_utc: AwareDatetime
    condition: str | None = Field(default=None, max_length=64)
    distance_m: float | None = Field(default=None, ge=0, le=20)
    posture: Posture | None = None
    paced_bpm: float | None = Field(default=None, ge=0, le=120)
    source_kind: SourceKind = SourceKind.csi

    @model_validator(mode="after")
    def _ordered(self) -> SessionMeta:
        if self.end_utc <= self.start_utc:
            raise ValueError("end_utc must be after start_utc")
        return self


class MotionValue(_Strict):
    t_start: AwareDatetime
    t_end: AwareDatetime
    motion: bool
    score: float | None = None


class WindowIn(_Strict):
    """WindowEstimate without session_id/run_id (taken from the batch / the run)."""

    t_start: AwareDatetime
    t_end: AwareDatetime
    rr_a: float | None = None
    rr_b: float | None = None
    pnr_db: float | None = None
    motion_flag: bool = False
    quality: float = 0.0
    presence: bool = True


class HeartIn(_Strict):
    t_start: AwareDatetime
    t_end: AwareDatetime
    hr_bpm: float | None = None
    quality: float = 0.0
    experimental: bool = True


class EstimateBatch(_Strict):
    """One session's device-side estimates. Either session_id (an existing session of
    the caller) or session (metadata for a new one) must be given."""

    session_id: str | None = None
    session: SessionMeta | None = None
    windows: list[WindowIn] = Field(default_factory=list)
    hearts: list[HeartIn] = Field(default_factory=list)
    motion: list[MotionValue] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self) -> EstimateBatch:
        if (self.session_id is None) == (self.session is None):
            raise ValueError("give exactly one of session_id or session")
        if not (self.windows or self.hearts):
            raise ValueError("batch has no estimates")
        for name, items in (("windows", self.windows), ("hearts", self.hearts)):
            starts = [w.t_start for w in items]
            if len(set(starts)) != len(starts):
                raise ValueError(f"duplicate t_start in {name}")
        keys = {(w.t_start, w.t_end) for w in self.windows}
        for m in self.motion:
            if (m.t_start, m.t_end) not in keys:
                raise ValueError("motion value does not match any window [t_start, t_end)")
        return self


def canonical_bytes(batch: EstimateBatch) -> bytes:
    """Canonical JSON (sorted keys, UTC ISO times): equal batches hash equally."""
    return json.dumps(batch.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()


def batch_sha256(batch: EstimateBatch) -> str:
    return hashlib.sha256(canonical_bytes(batch)).hexdigest()


def parse_batch(data: Any) -> EstimateBatch:
    """dict/str/bytes -> EstimateBatch, validating every element against the contracts."""
    try:
        batch = (
            EstimateBatch.model_validate_json(data)
            if isinstance(data, str | bytes)
            else EstimateBatch.model_validate(data)
        )
        sid = batch.session_id or "pending"
        for w in batch.windows:  # contract checks (bpm range, t_end > t_start, quality 0..1)
            WindowEstimate(session_id=sid, **w.model_dump())
        for h in batch.hearts:  # experimental must stay True (FR8)
            HeartEstimate(session_id=sid, **h.model_dump())
    except ValidationError as exc:
        errs = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()][:20]
        raise InjectionError("malformed estimate batch", errs) from None
    return batch


def _check_code_version(code_version: str | None) -> str:
    cv = (code_version or "").strip()
    if not cv or len(cv) > CODE_VERSION_MAX or not cv.isprintable():
        raise InjectionError(f"X-Code-Version is required (1..{CODE_VERSION_MAX} printable chars)")
    return cv


def _previous(db: Session, user_id: str, sha: str) -> PipelineRun | None:
    stmt = scoped(
        select(PipelineRun).where(
            PipelineRun.kind == KIND, PipelineRun.status == RunStatus.succeeded.value
        ),
        PipelineRun,
        user_id,
    )
    return next((r for r in db.scalars(stmt) if sha in (r.input_hashes or [])), None)


def _result(run: PipelineRun, duplicate: bool) -> dict[str, Any]:
    p = run.parameters
    return {
        "run_id": run.id,
        "session_id": p["session_id"],
        "batch_sha256": p["batch_sha256"],
        "windows": p["windows"],
        "hearts": p["hearts"],
        "motion": p["motion"],
        "code_version": run.code_version,
        "duplicate": duplicate,
    }


def _archive(sid: str, sha: str, payload: bytes) -> tuple[Path, bool]:
    """Write the batch read-only under DATA_DIR/raw/<sid>/. Returns (path, created)."""
    d = get_settings().data_dir / "raw" / sid
    p = d / f"estimates-{sha}.json"
    if p.exists():
        return p, False
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".estimates-{sha}.tmp"
    tmp.write_bytes(payload)
    os.chmod(tmp, stat.S_IRUSR | stat.S_IRGRP)
    os.replace(tmp, p)
    return p, True


def _remove_archive(p: Path) -> None:
    if p.exists():
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
        p.unlink()
    try:
        p.parent.rmdir()  # only if now empty
    except OSError:
        pass


def inject(db: Session, user_id: str, data: Any, code_version: str | None) -> dict[str, Any]:
    """Validate, then store one batch. Raises InjectionError (nothing written)."""
    cv = _check_code_version(code_version)
    batch = parse_batch(data)
    if db.get(User, user_id) is None:
        raise InjectionError("unknown user")
    sha = batch_sha256(batch)
    prev = _previous(db, user_id, sha)
    if prev is not None:
        return _result(prev, duplicate=True)

    if batch.session_id is not None:
        sess = db.get(CaptureSession, batch.session_id)
        if sess is None or sess.user_id != user_id:  # never reveal other users' sessions
            raise InjectionError("session not found")
        sid = sess.id
    else:
        sid = str(uuid.uuid5(_NS, f"{user_id}:{sha}"))
        if db.get(CaptureSession, sid) is not None:
            raise InjectionError("session for this batch already exists")

    path, created = _archive(sid, sha, canonical_bytes(batch))
    params = {
        "session_id": sid,
        "batch_sha256": sha,
        "archive": path.name,
        "windows": len(batch.windows),
        "hearts": len(batch.hearts),
        "motion": len(batch.motion),
        "client_code_version": cv,
    }
    rec = runs.create_run(db, KIND, params, [sha], user_id=user_id)
    done = runs.execute(db, rec.id)
    if done.status is not RunStatus.succeeded:
        if created:
            _remove_archive(path)
        raise InjectionError("estimate batch could not be stored", [done.log.splitlines()[-1]])
    return _result(db.get(PipelineRun, rec.id), duplicate=False)


def _apply(db: Session, run: PipelineRun) -> str:
    """Run handler: everything here commits with the run, or rolls back with it."""
    p = run.parameters
    uid, sid = run.user_id, p["session_id"]
    path = get_settings().data_dir / "raw" / sid / p["archive"]
    batch = parse_batch(path.read_bytes())
    if hashlib.sha256(canonical_bytes(batch)).hexdigest() != p["batch_sha256"]:
        raise ValueError("archived batch does not match its sha256")

    if batch.session is not None:
        m = batch.session
        db.add(
            CaptureSession(
                id=sid,
                user_id=uid,
                start_utc=m.start_utc,
                end_utc=m.end_utc,
                condition=m.condition,
                distance_m=m.distance_m,
                posture=m.posture.value if m.posture else None,
                paced_bpm=m.paced_bpm,
                source_kind=m.source_kind.value,
                raw_path=f"raw/{sid}",
                raw_sha256=p["batch_sha256"],
                usable=False,
                run_id=run.id,
            )
        )
        db.flush()
    for model in (WindowEstimateRow, HeartEstimateRow):
        db.execute(
            scoped(delete(model).where(model.session_id == sid), model, uid),
            execution_options={"synchronize_session": False},
        )
    moving = {(m.t_start, m.t_end): m.motion for m in batch.motion}
    db.add_all(
        WindowEstimateRow(
            user_id=uid,
            session_id=sid,
            run_id=run.id,
            **(w.model_dump() | {"motion_flag": moving.get((w.t_start, w.t_end), w.motion_flag)}),
        )
        for w in batch.windows
    )
    db.add_all(
        HeartEstimateRow(user_id=uid, session_id=sid, run_id=run.id, **h.model_dump())
        for h in batch.hearts
    )
    db.flush()
    run.code_version = p["client_code_version"]  # the code that produced the estimates
    return f"{KIND} session={sid} windows={p['windows']} hearts={p['hearts']} motion={p['motion']}"


RUN_KINDS = {KIND: _apply}


CSV_COLUMNS = (
    "kind",
    "t_start",
    "t_end",
    "rr_a",
    "rr_b",
    "pnr_db",
    "motion_flag",
    "quality",
    "presence",
    "hr_bpm",
    "motion",
    "score",
)


def batch_from_csv(text: str, *, session_id: str | None = None) -> dict[str, Any]:
    """Device CSV -> batch dict. One row per estimate; ``kind`` is window|heart|motion.

    Columns (blank = not given): kind,t_start,t_end,rr_a,rr_b,pnr_db,motion_flag,
    quality,presence,hr_bpm,motion,score. Without session_id the session spans the
    rows' earliest t_start to latest t_end. Validation happens in parse_batch.
    """
    import csv
    import io

    reader = csv.DictReader(io.StringIO(text))
    unknown = set(reader.fieldnames or ()) - set(CSV_COLUMNS)
    if not reader.fieldnames or "kind" not in reader.fieldnames or unknown:
        raise InjectionError(f"CSV header must use only {','.join(CSV_COLUMNS)} and have kind")

    def val(row: dict, key: str) -> Any:
        v = (row.get(key) or "").strip()
        if v == "":
            return None
        if v.lower() in ("true", "false"):
            return v.lower() == "true"
        try:
            return float(v)
        except ValueError:
            return v

    fields = {
        "window": ("rr_a", "rr_b", "pnr_db", "motion_flag", "quality", "presence"),
        "heart": ("hr_bpm", "quality"),
        "motion": ("motion", "score"),
    }
    out: dict[str, list] = {"windows": [], "hearts": [], "motion": []}
    target = {"window": "windows", "heart": "hearts", "motion": "motion"}
    for n, row in enumerate(reader, start=2):
        kind = (row.get("kind") or "").strip()
        if kind not in fields:
            raise InjectionError(f"CSV row {n}: kind must be window, heart or motion")
        item = {"t_start": row.get("t_start"), "t_end": row.get("t_end")}
        item |= {k: val(row, k) for k in fields[kind] if val(row, k) is not None}
        out[target[kind]].append(item)
    batch: dict[str, Any] = dict(out)
    if session_id:
        batch["session_id"] = session_id
    else:
        rows = out["windows"] + out["hearts"]
        if not rows:
            raise InjectionError("CSV has no window or heart rows")
        try:
            starts = [datetime.fromisoformat(str(r["t_start"])) for r in rows]
            ends = [datetime.fromisoformat(str(r["t_end"])) for r in rows]
            if any(t.tzinfo is None for t in starts + ends):
                raise ValueError("naive")
            first, last = min(starts), max(ends)
        except ValueError:
            raise InjectionError("CSV t_start/t_end must be ISO-8601 with a UTC offset") from None
        batch["session"] = {"start_utc": first.isoformat(), "end_utc": last.isoformat()}
    return batch

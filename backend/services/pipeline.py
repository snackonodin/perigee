"""process_session: raw capture files -> window and heart estimates (FR6, FR8, FR10).

Registered as run kind "process_session" with params {"session_id"}. A re-run
replaces the previous rows for that session inside the run's transaction, so
results are idempotent and every row carries the run that produced it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models import (
    CaptureSession,
    HeartEstimateRow,
    PipelineRun,
    Profile,
    RawFile,
    WindowEstimateRow,
    scoped,
)
from backend.services import runs
from csi_core import breath, heart
from csi_core.config import CoreConfig, get_config
from csi_core.load import read_rotating
from csi_core.preprocess import clean

# A night runs from local noon to the next local noon and is named by the evening
# date. Convention, not a tuned threshold.
NIGHT_SPLIT = time(12, 0)


# ----------------------------------------------------------------- night dates


def user_tz(db: Session, user_id: str) -> ZoneInfo:
    """Profile timezone, falling back to UTC when missing or unknown."""
    name = db.scalar(scoped(select(Profile.timezone), Profile, user_id))
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def night_date(ts: datetime, tz: ZoneInfo) -> date:
    """Local evening date of the night that contains ``ts``."""
    local = ts.astimezone(tz)
    return (local - timedelta(hours=NIGHT_SPLIT.hour, minutes=NIGHT_SPLIT.minute)).date()


def night_bounds_utc(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[start, end) in UTC of the night named ``day``."""
    a = datetime.combine(day, NIGHT_SPLIT, tzinfo=tz)
    b = datetime.combine(day + timedelta(days=1), NIGHT_SPLIT, tzinfo=tz)
    return a.astimezone(UTC), b.astimezone(UTC)


# ----------------------------------------------------------------- raw files


def resolve_raw_path(rel: str, data_dir: Path) -> Path:
    """RawFile.path is relative to DATA_DIR; refuse anything that escapes it."""
    base = data_dir.resolve()
    p = (base / rel).resolve()
    if not p.is_relative_to(base):
        raise ValueError("raw file path escapes DATA_DIR")
    return p


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def session_csi_files(db: Session, sess: CaptureSession, data_dir: Path) -> list[Path]:
    """The session's CSI files, scoped to its owner and checked against their hashes."""
    stmt = scoped(
        select(RawFile).where(RawFile.session_id == sess.id, RawFile.kind == "csi"),
        RawFile,
        sess.user_id,
    ).order_by(RawFile.path)
    paths: list[Path] = []
    for rf in db.scalars(stmt):
        p = resolve_raw_path(rf.path, data_dir)
        if _sha256(p) != rf.sha256:
            raise ValueError(f"raw file {rf.id} does not match its recorded sha256")
        paths.append(p)
    if not paths:
        raise ValueError(f"session {sess.id} has no csi raw files")
    return paths


# ----------------------------------------------------------------- the run


def process(
    db: Session, session_id: str, run_id: str | None, cfg: CoreConfig | None = None
) -> dict:
    """Estimate windows for one session and replace its previous estimates.

    Does not commit: runs.execute commits with the "succeeded" transition.
    """
    cfg = cfg or get_config()
    sess = db.get(CaptureSession, session_id)
    if sess is None:
        raise LookupError(f"session {session_id} not found")
    if not sess.usable:
        raise ValueError(
            f"session {session_id} is not usable (mean_rows_per_s="
            f"{sess.mean_rows_per_s:.1f} < capture.min_rows_per_s); refusing to process"
        )
    uid = sess.user_id
    files = session_csi_files(db, sess, get_settings().data_dir)

    df = read_rotating(files)
    windows = breath.estimate_windows(clean(df, cfg), sess.id, cfg)
    hearts = heart.estimate_windows(heart.clean_heart(df, cfg), sess.id, cfg)

    for model in (WindowEstimateRow, HeartEstimateRow):
        db.execute(
            scoped(delete(model).where(model.session_id == sess.id), model, uid),
            execution_options={"synchronize_session": False},
        )
    db.add_all(
        WindowEstimateRow(user_id=uid, **w.model_dump(exclude={"run_id"}), run_id=run_id)
        for w in windows
    )
    db.add_all(
        HeartEstimateRow(user_id=uid, **h.model_dump(exclude={"run_id"}), run_id=run_id)
        for h in hearts
    )
    db.flush()
    tz = user_tz(db, uid)
    nights = sorted({night_date(w.t_start, tz) for w in windows})
    return {
        "windows": len(windows),
        "valid_windows": sum(w.rr_a is not None for w in windows),
        "heart_windows": len(hearts),
        "nights": [d.isoformat() for d in nights],
    }


@runs.register("process_session")
def process_session(db: Session, run: PipelineRun) -> str:
    sid = run.parameters.get("session_id")
    if not sid:
        raise ValueError("process_session params must include session_id")
    out = process(db, sid, run.id)
    return (
        f"process_session windows={out['windows']} valid={out['valid_windows']} "
        f"heart={out['heart_windows']} nights={','.join(out['nights'])}"
    )


RUN_KINDS = {"process_session": process_session}

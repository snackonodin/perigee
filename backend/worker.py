"""Background worker: executes queued pipeline runs via runs.execute.

- start_worker() / stop_worker() are idempotent and safe from the app lifespan
  (call init_db() first). One worker thread per process; run a single API process
  (uvicorn --workers 1) or two processes could pick the same queued run.
- run_pending(db) does one synchronous pass; tests call it directly.
- On start, runs left "running" by a crash are marked failed ("interrupted").
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend import db as db_mod
from backend.models import PipelineRun, utcnow
from backend.schemas.contracts import RunStatus
from backend.services import runs

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_S = 2.0

_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop = threading.Event()


def recover_interrupted(db: Session) -> int:
    rows = db.scalars(select(PipelineRun).where(PipelineRun.status == RunStatus.running.value))
    n = 0
    for row in rows:
        row.status = RunStatus.failed.value
        row.finished = utcnow()
        row.log = row.log + f"{utcnow().isoformat()} failed: interrupted (worker restart)\n"
        n += 1
    db.commit()
    if n:
        log.warning("worker: marked %d interrupted runs as failed", n)
    return n


def run_pending(db: Session, limit: int | None = None) -> int:
    """Execute queued runs, oldest first. Returns how many were executed."""
    stmt = (
        select(PipelineRun.id)
        .where(PipelineRun.status == RunStatus.queued.value)
        .order_by(PipelineRun.created_at, PipelineRun.id)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    done = 0
    for run_id in db.scalars(stmt).all():
        if _stop.is_set() and _thread is not None and threading.current_thread() is _thread:
            break
        try:
            runs.execute(db, run_id)  # records failures on the run itself
            done += 1
        except (LookupError, ValueError):
            db.rollback()  # deleted or no longer queued: someone else took it
        except Exception as exc:  # never kill the loop; never log exception text
            db.rollback()
            log.error("worker: run %s crashed: %s", run_id, type(exc).__name__)
    return done


def _loop(interval_s: float) -> None:
    while True:
        try:
            with db_mod.SessionLocal() as db:
                run_pending(db)
        except Exception as exc:
            log.error("worker pass failed: %s", type(exc).__name__)
        if _stop.wait(interval_s):
            return


def start_worker(interval_s: float = DEFAULT_INTERVAL_S) -> bool:
    """Start the worker thread. Returns False if it was already running."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return False
        _stop.clear()
        try:
            with db_mod.SessionLocal() as db:
                recover_interrupted(db)
        except Exception as exc:
            log.error("worker recovery failed: %s", type(exc).__name__)
        _thread = threading.Thread(
            target=_loop, args=(interval_s,), name="astro-worker", daemon=True
        )
        _thread.start()
        log.info("worker started")
        return True


def stop_worker(timeout_s: float = 10.0) -> None:
    """Signal the worker and wait for the current run to finish. Safe if not started."""
    global _thread
    with _lock:
        t = _thread
        _stop.set()
        if t is not None and t.is_alive():
            t.join(timeout_s)
            if t.is_alive():
                log.warning("worker did not stop within %.0fs", timeout_s)
                return
        _thread = None


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()

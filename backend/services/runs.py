"""Pipeline runs (FR10): which code, parameters and inputs produced a result.

create_run() records a queued run. execute() moves it queued -> running ->
succeeded | failed, committing each transition, and stamps the code version
(git SHA) that actually executed. A handler's DB writes commit together with the
"succeeded" transition; on failure they are rolled back and the run is "failed".

Handlers are registered per kind with @register("kind"). Each takes
(db, run) and returns a short log string. Never put red-class data (survey
answers, notes, tokens) in params or logs.
"""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
from collections.abc import Callable
from functools import lru_cache

from sqlalchemy.orm import Session

from backend.models import PipelineRun, User, utcnow
from backend.schemas.contracts import RunRecord, RunStatus
from csi_core.config import ROOT

log = logging.getLogger(__name__)

Handler = Callable[[Session, PipelineRun], str]
_HANDLERS: dict[str, Handler] = {}
# Modules that define the built-in kinds (each exposes RUN_KINDS = {kind: handler}).
# Imported lazily, because they import this module.
_BUILTIN_MODULES = ("backend.services.pipeline", "backend.services.fusion")
_MAX_LOG = 20_000


def register(kind: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _HANDLERS[kind] = fn
        return fn

    return deco


def _load_builtins() -> None:
    """Make sure every built-in kind is in the registry.

    Registered explicitly from RUN_KINDS, not only by the import side effect,
    because a module is imported once while the registry can be swapped (tests).
    """
    for m in _BUILTIN_MODULES:
        for kind, fn in importlib.import_module(m).RUN_KINDS.items():
            _HANDLERS.setdefault(kind, fn)


def registered_kinds() -> list[str]:
    _load_builtins()
    return sorted(_HANDLERS)


@lru_cache(maxsize=1)
def code_version() -> str:
    """Git SHA of the running code (+ '-dirty'). ASTRO_CODE_VERSION overrides it,
    for devices that run from a copy without .git."""
    env = os.environ.get("ASTRO_CODE_VERSION")
    if env:
        return env
    try:
        out = subprocess.run(
            ["git", "describe", "--always", "--dirty", "--abbrev=40", "--match=NONE"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=5,
        )  # fmt: skip
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def to_record(row: PipelineRun) -> RunRecord:
    return RunRecord(
        id=row.id,
        kind=row.kind,
        parameters=row.parameters,
        code_version=row.code_version,
        input_hashes=row.input_hashes,
        status=RunStatus(row.status),
        started=row.started,
        finished=row.finished,
        log=row.log,
    )


def _append(row: PipelineRun, line: str) -> None:
    row.log = (row.log + f"{utcnow().isoformat()} {line}\n")[-_MAX_LOG:]


def create_run(
    db: Session,
    kind: str,
    params: dict,
    input_hashes: list[str],
    *,
    user_id: str | None = None,
) -> RunRecord:
    """Record a queued run. user_id owns the run (pipeline_runs.user_id, used by scoped()
    reads and by delete_user). If omitted, params["user_id"] is used when present; the two
    must agree. Global runs pass neither."""
    _load_builtins()
    if kind not in _HANDLERS:
        raise ValueError(f"unknown run kind {kind!r}; known: {registered_kinds()}")
    p_uid = params.get("user_id") if isinstance(params, dict) else None
    if user_id is None and isinstance(p_uid, str):
        # Fallback for callers that only put the owner in params. Best effort: an id that
        # is not a user must never break run creation, so the column stays NULL then.
        if db.get(User, p_uid) is not None:
            user_id = p_uid
    elif user_id is not None and p_uid is not None and p_uid != user_id:
        raise ValueError("user_id argument and params['user_id'] disagree")
    # Validate through the contract first (sha256 format, JSON-able params).
    rec = RunRecord(
        kind=kind,
        parameters=params,
        code_version=code_version(),
        input_hashes=sorted(set(input_hashes)),
    )
    row = PipelineRun(
        id=rec.id,
        kind=rec.kind,
        parameters=rec.parameters,
        code_version=rec.code_version,
        input_hashes=rec.input_hashes,
        status=RunStatus.queued.value,
        log="",
        user_id=user_id,
    )
    _append(row, f"queued code={rec.code_version}")
    db.add(row)
    db.commit()
    return to_record(row)


def execute(db: Session, run_id: str) -> RunRecord:
    _load_builtins()  # a worker may execute a run created before the import
    row = db.get(PipelineRun, run_id)
    if row is None:
        raise LookupError(f"run {run_id} not found")
    if row.status != RunStatus.queued.value:
        raise ValueError(f"run {run_id} is {row.status}, only queued runs can execute")

    row.status = RunStatus.running.value
    row.started = utcnow()
    row.code_version = code_version()
    _append(row, f"running code={row.code_version}")
    db.commit()

    try:
        msg = _HANDLERS[row.kind](db, row)
    except Exception as exc:  # recorded on the run; the caller inspects status
        db.rollback()
        row = db.get(PipelineRun, run_id)
        assert row is not None
        row.status = RunStatus.failed.value
        row.finished = utcnow()
        _append(row, f"failed {type(exc).__name__}: {str(exc)[:500]}")
        db.commit()
        log.warning("run %s (%s) failed: %s", run_id, row.kind, type(exc).__name__)
        return to_record(row)

    row.status = RunStatus.succeeded.value
    row.finished = utcnow()
    if msg:
        _append(row, msg)
    _append(row, "succeeded")
    db.commit()
    return to_record(row)

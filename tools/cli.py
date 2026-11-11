"""Operator CLI.

    python -m tools.cli ingest --user <id|email> DIR [DIR ...]
    python -m tools.cli process SESSION_ID
    python -m tools.cli process --nightly --user <id|email> --date YYYY-MM-DD
    python -m tools.cli reset-demo --yes
    python -m tools.cli seed-personas            (stub until the OPS-6 persona spec lands)
    python -m tools.cli export --user <id|email> --out FILE.json
    python -m tools.cli backup --out FILE.astrobk [--no-raw]
    python -m tools.cli restore FILE.astrobk [--force]   (stop the API first)

The DB comes from DATABASE_URL (settings) unless --db-url is given. Results are written
to stdout as JSON; diagnostics go to the (redacting) log on stderr.
Exit codes: 0 ok, 1 failed, 2 usage / not implemented.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend import db as db_mod
from backend.models import CaptureSession, RawFile, User, scoped
from backend.services import runs
from backend.services.ingestion import IngestError, ingest_session

log = logging.getLogger("tools.cli")

# Modules that register real run kinds (process_session, run_nightly) when present.
PIPELINE_MODULES = ("backend.services.pipeline", "backend.services.fusion")


def _out(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def _load_pipeline() -> None:
    for name in PIPELINE_MODULES:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as exc:
            if exc.name != name:  # the module exists but one of its imports is missing
                raise


def _resolve_user(db: Session, ref: str) -> User:
    user = db.get(User, ref)
    if user is None:
        user = db.scalars(select(User).where(User.email == ref.strip().lower())).one_or_none()
    if user is None:
        raise SystemExit(f"error: no such user {ref!r}")
    return user


# ----------------------------------------------------------------- commands


def cmd_ingest(db: Session, args: argparse.Namespace) -> int:
    user = _resolve_user(db, args.user)
    failed = 0
    results = []
    for d in args.dirs:
        try:
            rec = ingest_session(db, user.id, Path(d))
        except IngestError as exc:
            failed += 1
            results.append({"dir": str(d), "error": str(exc)})
            continue
        results.append({
            "dir": str(d), "session_id": rec.id, "files": len(rec.files),
            "rows": rec.stats.rows if rec.stats else 0, "usable": rec.usable,
        })  # fmt: skip
    _out(results)
    return 1 if failed else 0


def cmd_process(db: Session, args: argparse.Namespace) -> int:
    _load_pipeline()
    if args.nightly:
        if not (args.user and args.date):
            raise SystemExit("error: --nightly needs --user and --date")
        user = _resolve_user(db, args.user)
        night = date.fromisoformat(args.date)
        rec = runs.create_run(
            db, "run_nightly", {"user_id": user.id, "date": night.isoformat()}, [],
            user_id=user.id,
        )  # fmt: skip
    else:
        if not args.session_id:
            raise SystemExit("error: give SESSION_ID or --nightly")
        sess = db.get(CaptureSession, args.session_id)
        if sess is None:
            raise SystemExit(f"error: no such session {args.session_id!r}")
        hashes = db.scalars(
            scoped(select(RawFile.sha256), RawFile, sess.user_id).where(
                RawFile.session_id == sess.id
            )
        ).all()
        rec = runs.create_run(
            db, "process_session", {"session_id": sess.id, "user_id": sess.user_id},
            list(hashes), user_id=sess.user_id,
        )  # fmt: skip
    done = runs.execute(db, rec.id)
    _out(done.model_dump(mode="json"))
    return 0 if done.status == "succeeded" else 1


def cmd_reset_demo(db: Session, args: argparse.Namespace) -> int:
    """Delete every synthetic (persona) user with their rows and raw files.

    Real users (is_synthetic = 0) are never touched.
    """
    from backend.services.accounts import delete_user

    synthetic = db.scalars(select(User.id).where(User.is_synthetic.is_(True))).all()
    if not args.yes:
        _out({"would_delete_synthetic_users": len(synthetic), "hint": "re-run with --yes"})
        return 2
    for uid in synthetic:
        delete_user(db, uid)
    real_left = db.scalar(select(User.id).where(User.is_synthetic.is_(False)).limit(1))
    _out({"deleted_synthetic_users": len(synthetic), "real_users_kept": real_left is not None})
    return 0


def cmd_seed_personas(db: Session, args: argparse.Namespace) -> int:
    # Planned (coordinator, pending OPS-6 spec): synthetic is_synthetic users; historical
    # nights as synthetic night_features/window_estimates (source_kind=synthetic); only
    # the final demo night per persona through ingest_session at full rate.
    log.error("seed-personas is not implemented yet (waiting for the OPS-6 persona spec)")
    _out({"status": "not_implemented", "reason": "pending OPS-6 persona spec"})
    return 2


def cmd_export(db: Session, args: argparse.Namespace) -> int:
    """Write one user's data export (decrypted: red-class) to a new 0600 file."""
    from backend.services.accounts import export_user

    user = _resolve_user(db, args.user)
    out = Path(args.out)
    data = export_user(db, user.id)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)  # never overwrite
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True, default=str)
    _out({"user_id": user.id, "out": str(out)})
    return 0


# ----------------------------------------------------------------- parser


def cmd_backup(db: Session, args: argparse.Namespace) -> int:
    from backend.services.backup import BackupError, create_backup

    try:
        summary = create_backup(Path(args.out), include_raw=not args.no_raw)
    except BackupError as exc:
        log.error("backup failed: %s", exc)
        _out({"status": "failed", "error": str(exc)})
        return 1
    _out({"status": "ok", **asdict(summary)})
    return 0


def cmd_restore(db: Session, args: argparse.Namespace) -> int:
    from backend.services.backup import BackupError, RestoreRefused, restore_backup

    db.close()
    try:
        summary = restore_backup(Path(args.archive), force=args.force)
    except RestoreRefused as exc:
        _out({"status": "refused", "error": str(exc)})
        return 2
    except BackupError as exc:
        log.error("restore failed: %s", exc)
        _out({"status": "failed", "error": str(exc)})
        return 1
    _out({"status": "ok", **asdict(summary)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="astro", description="Astronaut Health Monitor operator CLI")
    p.add_argument("--db-url", help="override DATABASE_URL (default: from settings)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest", help="ingest capture folder(s), idempotent")
    s.add_argument("--user", required=True, help="user id or email")
    s.add_argument("dirs", nargs="+", type=Path)
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("process", help="run process_session or run_nightly with provenance")
    s.add_argument("session_id", nargs="?")
    s.add_argument("--nightly", action="store_true")
    s.add_argument("--user")
    s.add_argument("--date", help="YYYY-MM-DD (evening the night started)")
    s.set_defaults(fn=cmd_process)

    s = sub.add_parser("reset-demo", help="delete all synthetic users and their data")
    s.add_argument("--yes", action="store_true", help="actually delete")
    s.set_defaults(fn=cmd_reset_demo)

    s = sub.add_parser("seed-personas", help="(stub) create demo personas")
    s.set_defaults(fn=cmd_seed_personas)

    s = sub.add_parser("export", help="export one user's data to a JSON file")
    s.add_argument("--user", required=True, help="user id or email")
    s.add_argument("--out", required=True, help="output file (must not exist)")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("backup", help="encrypted DB snapshot + raw files (key from FIELD_KEY)")
    s.add_argument("--out", required=True, help="archive path (outside the repo; must not exist)")
    s.add_argument("--no-raw", action="store_true", help="manifest only, not the raw files")
    s.set_defaults(fn=cmd_backup)

    s = sub.add_parser("restore", help="verify, decrypt and restore a backup archive")
    s.add_argument("archive", type=Path)
    s.add_argument("--force", action="store_true", help="overwrite a non-empty DB / raw files")
    s.set_defaults(fn=cmd_restore)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from backend.logging import configure_logging

        configure_logging(logging.DEBUG if args.verbose else logging.INFO)
    except ImportError:  # pragma: no cover
        logging.basicConfig(level=logging.INFO)
    engine = db_mod.init_db(args.db_url)
    try:
        with db_mod.SessionLocal() as db:
            return args.fn(db, args)
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

"""Fixtures: a synth night registered as a session in a throwaway DATA_DIR.

register_session() is a minimal stand-in for b0's ingest_session (feat/db-ingest):
copy files under DATA_DIR/raw/<session_id>/, store relative paths and hashes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from backend import db as db_mod
from backend.config import get_settings
from backend.models import Base, CaptureSession, Profile, RawFile, User
from backend.schemas.contracts import new_id
from csi_core.config import get_config
from csi_core.load import capture_stats, read_rotating
from csi_core.synth import synth_night

NIGHT_START = datetime(2026, 11, 10, 22, 30, tzinfo=UTC)
NIGHT_HOURS = 3.2  # just over night.min_valid_hours
NIGHT_RR = 22.0


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    d = tmp_path / "astro-data"
    d.mkdir()
    monkeypatch.setenv("DATA_DIR", str(d))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{d / 'db' / 'astro.db'}")
    get_settings.cache_clear()
    yield d
    get_settings.cache_clear()


@pytest.fixture
def db(data_dir: Path) -> Iterator[Session]:
    eng: Engine = db_mod.init_db()
    Base.metadata.create_all(eng)
    with db_mod.SessionLocal() as s:
        yield s
    eng.dispose()
    db_mod.SessionLocal.configure(bind=None)


@pytest.fixture(scope="session")
def synth_files(tmp_path_factory: pytest.TempPathFactory) -> list[Path]:
    d = tmp_path_factory.mktemp("synth_night")
    return synth_night(
        d,
        start_utc=NIGHT_START,
        hours=NIGHT_HOURS,
        rr_bpm=NIGHT_RR,
        fs=10.0,
        n_sub=8,
        motion_bursts=4,
        absent_spans=[(3600.0, 3900.0)],
        seed=11,
    )


def make_user(db: Session, tz: str = "UTC") -> str:
    u = User(email=f"{new_id()}@example.test", password_hash="x", is_synthetic=True)
    db.add(u)
    db.flush()
    db.add(Profile(user_id=u.id, timezone=tz))
    db.commit()
    return u.id


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def register_session(db: Session, user_id: str, files: list[Path], data_dir: Path) -> str:
    sid = new_id()
    dest = data_dir / "raw" / sid
    dest.mkdir(parents=True)
    copied = [Path(shutil.copy2(f, dest / f.name)) for f in files]
    csi = [p for p in copied if p.name.startswith("csi_")]
    meta = json.loads((dest / "meta.json").read_text())
    stats = capture_stats(read_rotating(csi), get_config())
    combined = hashlib.sha256("".join(sorted(_sha(p) for p in copied)).encode()).hexdigest()
    sess = CaptureSession(
        id=sid,
        user_id=user_id,
        start_utc=datetime.fromisoformat(meta["start_utc"]),
        end_utc=datetime.fromisoformat(meta["end_utc"]),
        condition=meta["condition"],
        paced_bpm=meta["paced_bpm"],
        source_kind=meta["source_kind"],
        raw_path=f"raw/{sid}",
        raw_sha256=combined,
        usable=stats.mean_rows_per_s >= get_config().capture.min_rows_per_s,
        **stats.model_dump(),
    )
    db.add(sess)
    for p in copied:
        kind = "csi" if p.name.startswith("csi_") else p.suffix.lstrip(".")
        db.add(
            RawFile(
                user_id=user_id,
                session_id=sid,
                path=str(p.relative_to(data_dir)),
                sha256=_sha(p),
                size_bytes=p.stat().st_size,
                kind=kind,
            )
        )
    db.commit()
    return sid

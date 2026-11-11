"""Account delete on a real ingested synth night: 0 rows and 0 files left."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from backend.models import Base, CaptureSession, RawFile, User
from backend.services import accounts as acc
from backend.services.ingestion import ingest_session
from csi_core.synth import synth_night

PW = "long enough password"


def _night(out: Path, seed: int) -> Path:
    synth_night(
        out,
        start_utc=datetime(2026, 11, 1, 22, 0, tzinfo=UTC),
        hours=0.05,
        rr_bpm=14.0,
        motion_bursts=0,
        seed=seed,
    )
    return out


def _hashes(d: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir())}


def _user_rows(db, user_id: str) -> dict[str, int]:
    return {
        t.name: db.scalar(select(func.count()).select_from(t).where(t.c.user_id == user_id))
        for t in Base.metadata.sorted_tables
        if "user_id" in t.c
    }


def test_delete_after_real_ingest(db, data_dir, tmp_path) -> None:
    a = acc.signup(db, "a@b.co", PW)
    b = acc.signup(db, "b@b.co", PW)
    src_a, src_b = _night(tmp_path / "src_a", 1), _night(tmp_path / "src_b", 2)
    src_a_before = _hashes(src_a)

    rec_a = ingest_session(db, a.user_id, src_a)
    rec_b = ingest_session(db, b.user_id, src_b)
    sess_a = db.get(CaptureSession, rec_a.id)
    assert not Path(sess_a.raw_path).is_absolute()  # portable: relative to DATA_DIR
    dir_a = data_dir / sess_a.raw_path
    dir_b = data_dir / db.get(CaptureSession, rec_b.id).raw_path
    files_a = [
        data_dir / p for p in db.scalars(select(RawFile.path).where(RawFile.user_id == a.user_id))
    ]
    assert files_a and all(f.is_file() for f in files_a) and dir_a.is_dir()
    assert sum(_user_rows(db, a.user_id).values()) > 0

    acc.delete_user(db, a.user_id)  # DATA_DIR from settings

    assert _user_rows(db, a.user_id) == dict.fromkeys(_user_rows(db, a.user_id), 0)
    assert db.get(User, a.user_id) is None
    assert not dir_a.exists() and not any(f.exists() for f in files_a)
    assert list((data_dir / "raw").iterdir()) == [dir_b]  # nothing of A's left on disk
    # B untouched; the capture source folder is read-only input and stays as it was
    assert dir_b.is_dir() and sum(_user_rows(db, b.user_id).values()) > 0
    assert _hashes(src_a) == src_a_before

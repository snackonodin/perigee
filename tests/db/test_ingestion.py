from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from backend.models import Base, CaptureSession, Marker, RawFile, User, scoped
from backend.services import ingestion
from backend.services.ingestion import IngestError, ingest_session
from tests.db.conftest import write_capture

TABLES = (CaptureSession, RawFile, Marker)


@pytest.fixture
def schema(engine: Engine) -> Engine:
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def user(schema: Engine, db: Session) -> User:
    u = User(email="a@x", password_hash="x")
    db.add(u)
    db.commit()
    return u


def _counts(db: Session) -> dict[str, int]:
    return {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in TABLES}


def _tree_hashes(d: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir())}


def test_ingest_creates_rows_and_copies(
    db: Session, user: User, capture_dir: Path, data_dir: Path
) -> None:
    src_before = _tree_hashes(capture_dir)
    rec = ingest_session(db, user.id, capture_dir)

    assert _counts(db) == {"sessions": 1, "raw_files": 4, "markers": 4}
    assert sorted(f.kind for f in rec.files) == ["csi", "csi", "markers", "meta"]
    dest = data_dir / "raw" / rec.id
    assert _tree_hashes(dest) == src_before  # byte-identical copies
    assert _tree_hashes(capture_dir) == src_before  # source untouched
    assert all(not (p.stat().st_mode & 0o222) for p in dest.iterdir())  # read-only
    assert not list((data_dir / "raw").glob(".staging-*"))

    row = db.get(CaptureSession, rec.id)
    assert row.raw_path == f"raw/{rec.id}"  # relative to DATA_DIR: portable
    assert all(not f.path.startswith("/") for f in rec.files)
    assert rec.source_kind.value == "synthetic"


def test_capture_stats(db: Session, user: User, capture_dir: Path) -> None:
    s = ingest_session(db, user.id, capture_dir).stats
    assert s is not None
    assert s.rows == 12_000 - 3
    assert s.timestamp_wraps == 1
    assert s.rate_changes == 2
    assert s.gaps_over_50ms == 1 and s.max_gap_s == pytest.approx(0.2, abs=1e-6)
    assert s.duration_s == pytest.approx(599.95, abs=1e-3)
    csi_rows = sum(
        f.rows for f in ingest_session(db, user.id, capture_dir).files if f.kind == "csi"
    )
    assert csi_rows == s.rows


def test_usable_follows_config_min_rows_per_s(db: Session, user: User, capture_dir: Path) -> None:
    # Fixture is 20 rows/s; config min_rows_per_s (PLACEHOLDER) is 50.
    rec = ingest_session(db, user.id, capture_dir)
    assert rec.usable is False


def test_ingest_twice_is_idempotent(
    db: Session, user: User, capture_dir: Path, data_dir: Path
) -> None:
    first = ingest_session(db, user.id, capture_dir)
    counts = _counts(db)
    second = ingest_session(db, user.id, capture_dir)
    assert _counts(db) == counts
    assert second.id == first.id and second.files == first.files and second.stats == first.stats
    assert [p.name for p in (data_dir / "raw").iterdir()] == [first.id]


def test_same_content_in_another_folder_is_still_idempotent(
    db: Session, user: User, capture_dir: Path, tmp_path: Path
) -> None:
    first = ingest_session(db, user.id, capture_dir)
    copy = shutil.copytree(capture_dir, tmp_path / "copy")
    assert ingest_session(db, user.id, copy).id == first.id
    assert _counts(db)["sessions"] == 1


def test_overlapping_capture_is_refused(
    db: Session, user: User, capture_dir: Path, tmp_path: Path, data_dir: Path
) -> None:
    ingest_session(db, user.id, capture_dir)
    other = write_capture(tmp_path / "other", seed=99)
    shutil.copy(capture_dir / "csi_22.csv.gz", other / "csi_22.csv.gz")  # one shared file
    before = _counts(db)
    with pytest.raises(IngestError, match="already belong"):
        ingest_session(db, user.id, other)
    assert _counts(db) == before
    assert len(list((data_dir / "raw").iterdir())) == 1


def test_users_are_isolated(db: Session, user: User, capture_dir: Path) -> None:
    b = User(email="b@x", password_hash="x")
    db.add(b)
    db.commit()
    ra = ingest_session(db, user.id, capture_dir)
    rb = ingest_session(db, b.id, capture_dir)  # same files, different owner
    assert ra.id != rb.id
    a_files = db.scalars(scoped(select(RawFile), RawFile, user.id)).all()
    assert {f.session_id for f in a_files} == {ra.id}


@pytest.mark.parametrize(
    "breaker, match",
    [
        (lambda d: (d / "meta.json").unlink(), "meta.json missing"),
        (lambda d: (d / "meta.json").write_text("{not json"), "not valid JSON"),
        (lambda d: (d / "meta.json").write_text(json.dumps({"start_utc": "x"})), "invalid"),
        (lambda d: (d / "meta.json").write_text(json.dumps({"id": "x"})), "without id"),
        (lambda d: [p.unlink() for p in d.glob("csi_*")], "no csi_"),
        (lambda d: (d / "markers.csv").write_text("when,label\n"), "columns"),
    ],
)
def test_bad_folders_leave_nothing_behind(
    db: Session, user: User, capture_dir: Path, data_dir: Path, breaker, match: str
) -> None:
    breaker(capture_dir)
    with pytest.raises(IngestError, match=match):
        ingest_session(db, user.id, capture_dir)
    assert _counts(db) == {"sessions": 0, "raw_files": 0, "markers": 0}
    raw = data_dir / "raw"
    assert not raw.exists() or not any(raw.iterdir())


def test_unknown_user_rejected_before_copy(
    schema: Engine, db: Session, capture_dir: Path, data_dir: Path
) -> None:
    with pytest.raises(IngestError, match="unknown user"):
        ingest_session(db, "00000000-0000-0000-0000-000000000000", capture_dir)
    assert not (data_dir / "raw").exists()


def test_db_failure_removes_copied_folder(
    db: Session, user: User, capture_dir: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(db, "commit", boom)
    with pytest.raises(RuntimeError, match="disk full"):
        ingest_session(db, user.id, capture_dir)
    monkeypatch.undo()
    assert _counts(db) == {"sessions": 0, "raw_files": 0, "markers": 0}
    assert not any((data_dir / "raw").iterdir())


def test_stats_small_jitter_is_not_a_wrap(tmp_path: Path) -> None:
    import pandas as pd

    from csi_core.config import get_config

    p = tmp_path / "csi_00.csv.gz"
    pd.DataFrame(
        {
            "host_time_utc": [f"2026-11-10T00:00:0{i}.000000Z" for i in range(4)],
            "ts_us": [1_000_000, 999_990, 2_000_000, 3_000_000],  # tiny backwards jitter
            "rate": [11, 11, 11, 11],
            "a0": [1.0, 1.0, 1.0, 1.0],
        }
    ).to_csv(p, index=False, compression="gzip")
    s = ingestion.compute_capture_stats([p], get_config())
    assert s.timestamp_wraps == 0 and s.rows == 4


def test_ingests_real_synth_output(db: Session, user: User, tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from csi_core.synth import synth_night

    d = tmp_path / "synth"
    synth_night(
        d, start_utc=datetime(2026, 11, 10, 22, 55, tzinfo=UTC), hours=10 / 60, rr_bpm=15.0,
        fs=20.0, n_sub=12, motion_bursts=2, absent_spans=[(420.0, 480.0)], seed=7,
    )  # fmt: skip
    rec = ingest_session(db, user.id, d)
    assert rec.stats is not None and rec.stats.timestamp_wraps == 1
    assert sum(f.kind == "csi" for f in rec.files) == 2
    assert ingest_session(db, user.id, d).id == rec.id

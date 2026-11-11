"""Property tests (Hypothesis) for ingest_session on random synthetic captures.

Each example gets its own DATA_DIR and DB: function-scoped pytest fixtures are not
reset between Hypothesis examples, so the store is built inside the test.
"""

from __future__ import annotations

import gzip
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import db as db_mod
from backend.config import get_settings
from backend.models import Base, CaptureSession, Marker, RawFile, User
from backend.services.ingestion import ingest_session, sha256_file
from csi_core.synth import synth_night

PROPS = settings(
    max_examples=12,
    database=None,  # no example DB in the repo; pytest-randomly seeds make runs reproducible
    deadline=None,  # synth + ingest is I/O bound; timing varies by machine
    suppress_health_check=[HealthCheck.too_slow],
)


@st.composite
def captures(draw) -> dict:
    """Random but small synth parameters. Starts near the top of the hour so most
    examples rotate into two hourly files."""
    minute = draw(st.integers(50, 59))
    second = draw(st.integers(0, 59))
    return {
        "start_utc": datetime(2026, 11, 10, 22, minute, second, tzinfo=UTC)
        + timedelta(days=draw(st.integers(0, 30))),
        "hours": draw(st.floats(0.004, 0.03, allow_nan=False)),  # ~15 s to ~2 min
        "fs": draw(st.floats(50.0, 120.0, allow_nan=False)),
        "rr_bpm": draw(st.floats(8.0, 30.0, allow_nan=False)),
        "n_sub": draw(st.integers(2, 12)),
        "motion_bursts": draw(st.integers(0, 3)),
        "seed": draw(st.integers(0, 2**31 - 1)),
    }


@contextmanager
def _store() -> Iterator[tuple[Session, str, Path]]:
    with tempfile.TemporaryDirectory() as tmp, pytest.MonkeyPatch.context() as mp:
        d = Path(tmp) / "astro-data"
        d.mkdir()
        mp.setenv("DATA_DIR", str(d))
        mp.setenv("DATABASE_URL", f"sqlite:///{d / 'db' / 'astro.db'}")
        get_settings.cache_clear()
        prev_bind = db_mod.SessionLocal.kw.get("bind")
        eng = db_mod.init_db()
        try:
            Base.metadata.create_all(eng)
            with db_mod.SessionLocal() as db:
                u = User(email="prop@x", password_hash="x")
                db.add(u)
                db.commit()
                yield db, u.id, Path(tmp)
        finally:
            eng.dispose()
            db_mod.SessionLocal.configure(bind=prev_bind)
            get_settings.cache_clear()


def _csv_rows(path: Path) -> int:
    with gzip.open(path, "rt") as fh:
        return sum(1 for _ in fh) - 1  # minus header


def _counts(db: Session) -> tuple[int, int, int]:
    return tuple(
        db.scalar(select(func.count()).select_from(m)) for m in (CaptureSession, RawFile, Marker)
    )


@PROPS
@given(params=captures())
def test_rows_conserved_and_reingest_is_noop(params: dict) -> None:
    with _store() as (db, uid, tmp):
        src = tmp / "capture"
        synth_night(src, **params)
        csv_files = sorted(src.glob("csi_*.csv.gz"))
        expected_rows = sum(_csv_rows(p) for p in csv_files)

        rec = ingest_session(db, uid, src)
        assert rec.stats is not None
        # rows conserved: every CSV row is counted once, per file and in total
        assert rec.stats.rows == expected_rows
        per_file = {f.path.rsplit("/", 1)[-1]: f.rows for f in rec.files if f.kind == "csi"}
        assert per_file == {p.name: _csv_rows(p) for p in csv_files}
        assert sum(per_file.values()) == expected_rows
        assert rec.stats.timestamp_wraps <= 1  # synth starts half a capture before a wrap

        counts = _counts(db)
        again = ingest_session(db, uid, src)
        assert again.id == rec.id and again.files == rec.files and again.stats == rec.stats
        assert _counts(db) == counts


@PROPS
@given(params=captures())
def test_hashes_stable_and_match_disk(params: dict) -> None:
    with _store() as (db, uid, tmp):
        a, b = tmp / "a", tmp / "b"
        synth_night(a, **params)
        synth_night(b, **params)  # same params -> byte-identical files
        names = sorted(p.name for p in a.iterdir())
        assert names == sorted(p.name for p in b.iterdir())
        assert all(sha256_file(a / n) == sha256_file(b / n) for n in names)

        rec = ingest_session(db, uid, a)
        assert ingest_session(db, uid, b).id == rec.id  # same content, other folder
        data_dir = get_settings().data_dir
        for f in rec.files:
            stored = data_dir / f.path
            assert sha256_file(stored) == f.sha256 == sha256_file(a / stored.name)
        assert len(rec.files) == len(names)

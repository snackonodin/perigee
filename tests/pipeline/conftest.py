"""Fixtures: a throwaway DATA_DIR + DB and one synthetic night (ingested by tests)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from backend import db as db_mod
from backend.config import get_settings
from backend.models import Base, Profile, User
from backend.schemas.contracts import new_id
from csi_core.synth import synth_night

NIGHT_START = datetime(2026, 11, 10, 22, 30, tzinfo=UTC)
NIGHT_HOURS = 3.2  # just over night.min_valid_hours
NIGHT_RR = 22.0
FS = 60.0  # stays above capture.min_rows_per_s (50) after synth packet drops


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
def synth_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("synth_night")
    synth_night(
        d,
        start_utc=NIGHT_START,
        hours=NIGHT_HOURS,
        rr_bpm=NIGHT_RR,
        fs=FS,
        n_sub=4,
        motion_bursts=4,
        absent_spans=[(3600.0, 3900.0)],
        seed=11,
    )
    return d


def make_user(db: Session, tz: str = "UTC") -> str:
    u = User(email=f"{new_id()}@example.test", password_hash="x", is_synthetic=True)
    db.add(u)
    db.flush()
    db.add(Profile(user_id=u.id, timezone=tz))
    db.commit()
    return u.id

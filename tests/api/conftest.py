"""Fixtures: a throwaway DATA_DIR and SQLite DB (schema via create_all) per test."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from backend import db as db_mod
from backend.config import get_settings
from backend.models import Base


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
def engine(data_dir: Path) -> Iterator[Engine]:
    eng = db_mod.init_db()
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()
    db_mod.SessionLocal.configure(bind=None)


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with db_mod.SessionLocal() as s:
        yield s

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


@pytest.fixture(autouse=True)
def _fresh_login_limiter() -> Iterator[None]:
    """Login failure counts live in process memory: never let them leak between tests."""
    from backend.security import reset_login_limiter

    reset_login_limiter()
    yield
    reset_login_limiter()


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    d = tmp_path / "astro-data"
    d.mkdir()
    monkeypatch.setenv("DATA_DIR", str(d))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{d / 'db' / 'astro.db'}")
    # tests never open the real ESP receiver, whatever this machine's .env says
    monkeypatch.setenv("MONITOR_SERIAL_PORT", "")
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


def build_app():
    """The accounts routers on a bare app, wired the way main.py will wire them."""
    from fastapi import FastAPI

    from backend.api.v1 import auth, me
    from backend.errors import install_error_handlers

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(me.router)
    return app


@pytest.fixture
def api(engine):
    from fastapi.testclient import TestClient

    with TestClient(build_app(), raise_server_exceptions=False) as c:
        yield c

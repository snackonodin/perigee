"""SQLAlchemy engine and session factory.

The SQLite database lives under DATA_DIR (outside the repo, which sits in
Google Drive: Drive sync corrupts WAL files). Every connection gets
foreign_keys=ON, journal_mode=WAL and busy_timeout=5000.

Usage: call ``init_db()`` once at startup (API, CLI, test fixture). It builds the
engine and binds ``SessionLocal`` to it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings
from csi_core.config import ROOT

SessionLocal: sessionmaker = sessionmaker(autoflush=False, expire_on_commit=False)


def _set_sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
    finally:
        cur.close()


def sqlite_path(url: str) -> Path | None:
    """File path of a sqlite URL, or None for in-memory / non-sqlite URLs."""
    u = make_url(url)
    if not u.drivername.startswith("sqlite") or u.database in (None, "", ":memory:"):
        return None
    return Path(u.database).expanduser().resolve()


def _assert_outside_repo(path: Path) -> None:
    if path.is_relative_to(ROOT.resolve()):
        raise RuntimeError(
            f"refusing to place the database inside the repo ({path}); "
            "set DATABASE_URL to a path under DATA_DIR"
        )


def default_url() -> str:
    return get_settings().database_url


def get_engine(url: str | None = None) -> Engine:
    """Build an engine. Defaults to DATABASE_URL from settings (under DATA_DIR)."""
    url = url or default_url()
    path = sqlite_path(url)
    connect_args: dict[str, Any] = {}
    if make_url(url).drivername.startswith("sqlite"):
        connect_args["check_same_thread"] = False  # FastAPI uses a threadpool
    if path is not None:
        _assert_outside_repo(path)
        path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args=connect_args)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


def init_db(url: str | None = None) -> Engine:
    """Create the engine and bind SessionLocal to it. Returns the engine."""
    engine = get_engine(url)
    SessionLocal.configure(bind=engine)
    return engine

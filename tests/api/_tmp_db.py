"""TEMPORARY stand-in for backend/db.py (feat/db-ingest, commit 0c61ba9).

Same public shape: ``SessionLocal`` (unbound until ``init_db``) and ``init_db(url)``.
At merge the coordinator repoints ``from tests.api._tmp_db import ...`` to ``backend.db``
and deletes this file.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker

SessionLocal: sessionmaker = sessionmaker(autoflush=False, expire_on_commit=False)


def _pragmas(dbapi_conn: Any, _record: Any) -> None:
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
    finally:
        cur.close()


def init_db(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _pragmas)
    SessionLocal.configure(bind=engine)
    return engine

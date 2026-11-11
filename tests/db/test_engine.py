from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from backend.db import get_engine, sqlite_path
from csi_core.config import ROOT


def test_pragmas_set_on_every_connection(engine: Engine) -> None:
    for _ in range(2):
        with engine.connect() as c:
            assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1
            assert c.execute(text("PRAGMA journal_mode")).scalar() == "wal"
            assert c.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_db_file_lives_under_data_dir(engine: Engine, data_dir: Path) -> None:
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    path = sqlite_path(str(engine.url))
    assert path is not None and path.is_relative_to(data_dir.resolve())
    assert path.exists()


def test_refuses_db_inside_repo() -> None:
    with pytest.raises(RuntimeError, match="inside the repo"):
        get_engine(f"sqlite:///{ROOT / 'astro.db'}")
    assert not (ROOT / "astro.db").exists()


def test_in_memory_url_is_allowed() -> None:
    eng = get_engine("sqlite://")
    with eng.connect() as c:
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1

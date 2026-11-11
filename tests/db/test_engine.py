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


SENTINEL = "sentinel-answer-7f3c91"


def _leak_paths(eng, caplog: pytest.LogCaptureFixture) -> str:
    """Run a bound INSERT with echo + INFO logging, plus a failing statement; return
    everything that was logged or raised."""
    import logging

    caplog.set_level(logging.INFO, logger="sqlalchemy.engine")
    eng.echo = True
    with eng.begin() as c:
        c.execute(text("CREATE TABLE t (v TEXT UNIQUE)"))
        c.execute(text("INSERT INTO t (v) VALUES (:v)"), {"v": SENTINEL})
    err = ""
    try:
        with eng.begin() as c:
            c.execute(text("INSERT INTO t (v) VALUES (:v)"), {"v": SENTINEL})  # UNIQUE fails
    except Exception as exc:  # noqa: BLE001 - we inspect the message
        err = str(exc)
    eng.dispose()
    return caplog.text + "\n" + err


def test_sql_logging_and_errors_never_show_bound_values(
    data_dir, caplog: pytest.LogCaptureFixture
) -> None:
    out = _leak_paths(get_engine(f"sqlite:///{data_dir / 'leak.db'}"), caplog)
    assert "INSERT INTO t" in out and "UNIQUE" in out  # the paths really ran
    assert SENTINEL not in out


def test_leak_check_detects_a_leak_without_hide_parameters(
    data_dir, caplog: pytest.LogCaptureFixture
) -> None:
    """Control: the same check on a plain engine does see the value, so the test above
    would catch a regression."""
    from sqlalchemy import create_engine

    out = _leak_paths(create_engine(f"sqlite:///{data_dir / 'control.db'}"), caplog)
    assert SENTINEL in out

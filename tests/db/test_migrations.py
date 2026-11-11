from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from backend.db import get_engine
from backend.models import Base
from csi_core.config import ROOT


def _cfg(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture
def url(data_dir: Path) -> str:
    return f"sqlite:///{data_dir / 'db' / 'migrate.db'}"


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_downgrade_upgrade_roundtrip(url: str) -> None:
    cfg = _cfg(url)
    engine = get_engine(url)
    expected = set(Base.metadata.tables)

    command.upgrade(cfg, "head")
    assert _tables(engine) == expected
    assert "v_real_users" in inspect(engine).get_view_names()

    command.downgrade(cfg, "base")
    engine.dispose()
    assert _tables(engine) == set()
    assert inspect(engine).get_view_names() == []

    command.upgrade(cfg, "head")
    engine.dispose()
    assert _tables(engine) == expected
    with engine.connect() as c:
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1
    engine.dispose()


def test_migrations_match_models(url: str) -> None:
    command.upgrade(_cfg(url), "head")
    engine = get_engine(url)
    with engine.connect() as c:
        mc = MigrationContext.configure(c, opts={"compare_type": False})
        diff = compare_metadata(mc, Base.metadata)
    engine.dispose()
    assert diff == [], f"models and migrations drifted; run alembic revision --autogenerate: {diff}"

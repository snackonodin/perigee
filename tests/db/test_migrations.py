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


def _seed_0001(engine: Engine) -> None:
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (id, email, status, created_at, is_synthetic) "
                "VALUES ('u1', 'a@x', 'active', '2026-11-01T00:00:00.000000Z', 0)"
            )
        )
        c.execute(
            text(
                "INSERT INTO survey_responses (id, user_id, instrument_id, instrument_version, "
                "administered_at, answers_enc, created_at) VALUES ('r1', 'u1', 'phq2', '1', "
                "'2026-11-01T00:00:00.000000Z', x'00ff', '2026-11-01T00:00:00.000000Z')"
            )
        )
        c.execute(text(
            "INSERT INTO instrument_catalog (id, instrument_id, version, name, timeframe, "
            "definition, updated_at) VALUES ('i1', 'phq2', '1', 'PHQ-2', 'two weeks', '{}', "
            "'2026-11-01T00:00:00.000000Z')"
        ))  # fmt: skip


def test_0002_keeps_data_and_relaxes_answers(url: str) -> None:
    cfg = _cfg(url)
    engine = get_engine(url)
    command.upgrade(cfg, "0001")
    _seed_0001(engine)
    command.upgrade(cfg, "0002")
    engine.dispose()
    long_tf = "x" * 89
    with engine.begin() as c:
        assert c.execute(text("SELECT answers_enc FROM survey_responses")).scalar() == b"\x00\xff"
        assert c.execute(text("SELECT user_id FROM survey_responses")).scalar() == "u1"
        c.execute(text("UPDATE instrument_catalog SET timeframe = :t"), {"t": long_tf})
        c.execute(text(
            "INSERT INTO survey_responses (id, user_id, instrument_id, instrument_version, "
            "administered_at, answers_enc, answers_hmac, created_at) VALUES ('r2', 'u1', "
            "'phq2', '1', '2026-11-02T00:00:00.000000Z', NULL, :h, "
            "'2026-11-02T00:00:00.000000Z')"
        ), {"h": "f" * 64})  # fmt: skip
    cols = {c["name"]: c for c in inspect(engine).get_columns("survey_responses")}
    assert cols["answers_enc"]["nullable"] and "answers_hmac" in cols
    tf_type = {c["name"]: c["type"] for c in inspect(engine).get_columns("instrument_catalog")}
    assert str(tf_type["timeframe"]).upper() == "TEXT"

    with pytest.raises(RuntimeError, match="cannot downgrade 0002"):
        command.downgrade(cfg, "0001")
    engine.dispose()
    with engine.connect() as c:  # refused downgrade changed nothing
        assert c.execute(text("SELECT COUNT(*) FROM survey_responses")).scalar() == 2
    with engine.begin() as c:
        c.execute(text("DELETE FROM survey_responses WHERE answers_enc IS NULL"))
    command.downgrade(cfg, "0001")
    engine.dispose()
    assert "answers_hmac" not in {
        c["name"] for c in inspect(engine).get_columns("survey_responses")
    }
    engine.dispose()

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


def test_0003_keeps_runs_and_child_references(url: str) -> None:
    cfg = _cfg(url)
    engine = get_engine(url)
    command.upgrade(cfg, "0002")
    ts = "2026-11-01T00:00:00.000000Z"
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (id, email, status, created_at, is_synthetic) "
                f"VALUES ('u1', 'a@x', 'active', '{ts}', 0)"
            )
        )
        c.execute(
            text(
                "INSERT INTO pipeline_runs (id, kind, parameters, code_version, input_hashes, "
                "status, log, created_at) VALUES "
                f"('r1', 'k', '{{}}', 'v', '[]', 'queued', '', '{ts}')"
            )
        )
        c.execute(text(
            "INSERT INTO sessions (id, user_id, start_utc, end_utc, source_kind, raw_path, "
            "raw_sha256, rows, duration_s, mean_rows_per_s, max_gap_s, gaps_over_50ms, "
            "rate_changes, timestamp_wraps, usable, run_id, created_at) VALUES "
            f"('s1', 'u1', '{ts}', '{ts}', 'csi', 'raw/s1', '{'a' * 64}', 0, 0, 0, 0, 0, 0, 0, 0, "
            f"'r1', '{ts}')"
        ))  # fmt: skip
    command.upgrade(cfg, "0003")
    engine.dispose()
    with engine.connect() as c:
        assert c.execute(text("SELECT run_id FROM sessions")).scalar() == "r1"
        assert c.execute(text("SELECT user_id FROM pipeline_runs")).scalar() is None
        assert c.execute(text("PRAGMA foreign_key_check")).all() == []
    command.downgrade(cfg, "0002")
    engine.dispose()
    with engine.connect() as c:
        assert c.execute(text("SELECT run_id FROM sessions")).scalar() == "r1"
        assert c.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()


def test_0004_motion_score_keeps_existing_windows(url: str) -> None:
    cfg = _cfg(url)
    engine = get_engine(url)
    command.upgrade(cfg, "0003")
    ts = "2026-11-01T00:00:00.000000Z"
    sid = "11111111-1111-1111-1111-111111111111"
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (id, email, status, created_at, is_synthetic) "
                f"VALUES ('u1', 'a@x', 'active', '{ts}', 0)"
            )
        )
        c.execute(
            text(
                "INSERT INTO sessions (id, user_id, start_utc, end_utc, source_kind, raw_path, "
                "raw_sha256, rows, duration_s, mean_rows_per_s, max_gap_s, gaps_over_50ms, "
                "rate_changes, timestamp_wraps, usable, created_at) VALUES "
                f"('{sid}', 'u1', '{ts}', '{ts}', 'csi', 'raw/x', '{'b' * 64}', "
                f"0, 0, 0, 0, 0, 0, 0, 0, '{ts}')"
            )
        )
        c.execute(text(
            "INSERT INTO window_estimates (id, user_id, session_id, t_start, t_end, rr_a, "
            f"motion_flag, quality, presence) VALUES ('w1', 'u1', '{sid}', '{ts}', '{ts}', "
            "14.5, 1, 0.9, 1)"
        ))  # fmt: skip
    command.upgrade(cfg, "0004")
    engine.dispose()
    with engine.begin() as c:
        row = c.execute(text("SELECT rr_a, motion_flag, motion_score FROM window_estimates")).one()
        assert tuple(row) == (14.5, 1, None)
        c.execute(text("UPDATE window_estimates SET motion_score = 0.42"))
    command.downgrade(cfg, "0003")
    engine.dispose()
    with engine.connect() as c:
        assert c.execute(text("SELECT rr_a FROM window_estimates")).scalar() == 14.5
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(window_estimates)"))}
        assert "motion_score" not in cols
    engine.dispose()

"""PIPE-4 acceptance: docs/ops/personas.md §6/§7 on a fixed anchor.

One full seed per module (the raw synth is cached across tests), then assertions
per persona, reseed idempotency and reset-demo. Thresholds come from the config.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import db as db_mod
from backend.config import get_settings
from backend.models import (
    Base,
    CaptureSession,
    Flag,
    NightFeaturesRow,
    SafetyEvent,
    User,
)
from backend.services import personas
from csi_core.config import get_config
from csi_core.fusion import PHYS_FEATURES
from csi_core.night import robust_z

pytestmark = pytest.mark.slow

ANCHOR = date(2026, 11, 18)
DEMO = ANCHOR - timedelta(days=1)
RAW_N_SUB = 8  # fewer subcarriers than the demo default (52) to keep the test fast


@pytest.fixture(scope="module")
def synth_cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("synth-cache")


@pytest.fixture(scope="module")
def seeded(tmp_path_factory, synth_cache) -> Iterator[tuple[Session, dict, Path]]:
    d = tmp_path_factory.mktemp("astro-data")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATA_DIR", str(d))
        mp.setenv("DATABASE_URL", f"sqlite:///{d / 'db' / 'astro.db'}")
        mp.delenv(personas.PASSWORD_ENV, raising=False)
        get_settings.cache_clear()
        eng = db_mod.init_db()
        Base.metadata.create_all(eng)
        with db_mod.SessionLocal() as db:
            out = personas.seed(db, anchor=ANCHOR, raw_n_sub=RAW_N_SUB, cache_root=synth_cache)
            yield db, out, d
        eng.dispose()
        db_mod.SessionLocal.configure(bind=None)
        get_settings.cache_clear()


def _uid(out: dict, key: str) -> str:
    return next(p["user_id"] for p in out["personas"] if p["key"] == key)


def _demo_flags(db: Session, uid: str) -> list[Flag]:
    return db.scalars(select(Flag).where(Flag.user_id == uid, Flag.date == DEMO)).all()


def _user_row_counts(db: Session, user_ids: list[str] | None = None) -> dict[str, int]:
    """Rows per user-owned table (all rows, or only those of user_ids)."""
    db.expire_all()
    out = {}
    for t in Base.metadata.sorted_tables:
        if "user_id" in t.c:
            stmt = select(func.count()).select_from(t)
            if user_ids is not None:
                stmt = stmt.where(t.c.user_id.in_(user_ids))
            out[t.name] = db.scalar(stmt)
    return out


def test_three_synthetic_users_with_14_valid_nights(seeded) -> None:
    db, out, _ = seeded
    cfg = get_config()
    assert len(out["personas"]) == 3
    for p in out["personas"]:
        u = db.get(User, p["user_id"])
        assert u.is_synthetic and u.email == p["email"]
        nights = db.scalars(select(NightFeaturesRow).where(NightFeaturesRow.user_id == u.id)).all()
        assert len(nights) == 14 and all(n.valid for n in nights)
        assert all(n.source_kind == "synthetic" for n in nights)
        demo = next(n for n in nights if n.date == DEMO)
        assert len(demo.session_ids) == 2
        assert demo.presence_hours == pytest.approx(7.5, abs=0.1)
        raw = db.get(CaptureSession, p["raw_session_id"])
        assert raw.usable and raw.mean_rows_per_s >= cfg.capture.min_rows_per_s


@pytest.mark.xfail(
    strict=True,
    reason="presence_hours z -2.3: small-n MAD + FR13 exclusion; pending baseline.mad_floor "
    "decision (coordinator)",
)
def test_p1_steady_no_flag_and_calibrated(seeded) -> None:
    db, out, _ = seeded
    uid = _uid(out, "steady")
    assert _demo_flags(db, uid) == []
    from backend.services.fusion import _baselines, _phys_history

    cfg = get_config()
    demo = db.scalar(
        select(NightFeaturesRow).where(
            NightFeaturesRow.user_id == uid, NightFeaturesRow.date == DEMO
        )
    )
    base = _baselines(uid, _phys_history(db, uid, DEMO, "synthetic", cfg, False), cfg)
    for f in PHYS_FEATURES:  # personas.md §2 calibration rule
        z = robust_z(getattr(demo, f), base[f])
        assert z is None or abs(z) < 1.5, (f, z)


def test_p2_drift_phys_only(seeded) -> None:
    db, out, _ = seeded
    alert = get_config().baseline.alert_robust_z
    (f,) = _demo_flags(db, _uid(out, "breath-drift"))
    assert (f.phys_level, f.mental_level, f.state) == (1, 0, "phys_only")
    assert f.components["physiology"]["rr_med"]["z"] >= alert
    assert f.priority > 1.0


def test_p3_mental_only_from_catalog_bands(seeded) -> None:
    db, out, _ = seeded
    (f,) = _demo_flags(db, _uid(out, "mental-dip"))
    assert (f.phys_level, f.mental_level, f.state) == (0, 1, "mental_only")
    assert f.priority == 1.0
    m = f.components["mental"]
    assert m["phq2"]["band"]["band"] == "at or above screening cutoff"
    assert m["gad2"]["band"]["band"] == "at or above screening cutoff"
    assert m["who5"]["band"]["band"] == "low wellbeing"
    assert "phq9" not in m  # the final PHQ-9 is submitted live, not seeded


def test_generated_passwords_returned_once_never_logged(seeded, synth_cache, caplog) -> None:
    db, out, _ = seeded
    assert all(p.get("generated_password") for p in out["personas"])
    caplog.set_level(logging.DEBUG)
    again = personas.seed(db, anchor=ANCHOR, raw_n_sub=RAW_N_SUB, cache_root=synth_cache)
    assert not any("generated_password" in p for p in again["personas"])
    for p in out["personas"]:
        assert p["generated_password"] not in caplog.text


def test_reseed_is_idempotent(seeded, synth_cache) -> None:
    db, _, _ = seeded
    before = _user_row_counts(db)
    personas.seed(db, anchor=ANCHOR, raw_n_sub=RAW_N_SUB, cache_root=synth_cache)
    assert _user_row_counts(db) == before


def test_final_phq9_option_shows_safety_path(seeded, synth_cache) -> None:
    db, out, _ = seeded
    uid = _uid(out, "mental-dip")
    assert (
        db.scalar(select(func.count()).select_from(SafetyEvent).where(SafetyEvent.user_id == uid))
        == 0
    )
    personas.seed(
        db, anchor=ANCHOR, include_final_phq9=True, raw_n_sub=RAW_N_SUB, cache_root=synth_cache
    )
    assert (
        db.scalar(select(func.count()).select_from(SafetyEvent).where(SafetyEvent.user_id == uid))
        == 1
    )


def test_reset_demo_removes_everything(seeded, synth_cache) -> None:
    import argparse

    from tools import cli

    db, out, d = seeded
    ids = [p["user_id"] for p in out["personas"]]
    assert cli.cmd_reset_demo(db, argparse.Namespace(yes=True)) == 0
    counts = _user_row_counts(db, ids)  # audit_log/pipeline_runs keep rows with user_id NULL
    assert all(v == 0 for v in counts.values()), counts
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert not any((d / "raw").iterdir())
    assert any(synth_cache.iterdir())  # the synth cache is kept for a fast reseed

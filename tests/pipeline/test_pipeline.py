"""Synth night -> register -> process_session -> run_nightly -> night_features + flag."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import (
    Baseline,
    Flag,
    HeartEstimateRow,
    NightFeaturesRow,
    PipelineRun,
    WindowEstimateRow,
)
from backend.schemas.contracts import RunStatus
from backend.services import fusion, pipeline, runs
from backend.services.ingestion import ingest_session

from .conftest import NIGHT_RR, make_user

NIGHT = date(2026, 11, 10)
TABLES = (WindowEstimateRow, HeartEstimateRow, NightFeaturesRow, Flag, Baseline)


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def _seed_history(db: Session, uid: str, n: int = 6, rr: float = 15.0) -> None:
    """Earlier valid, non-flagged synthetic nights so the baseline has left warm-up."""
    for i in range(1, n + 1):
        d = NIGHT - timedelta(days=i)
        on = datetime(d.year, d.month, d.day, 23, tzinfo=UTC)
        db.add(
            NightFeaturesRow(
                user_id=uid,
                date=d,
                rr_med=rr + (i % 3 - 1) * 0.5,
                rr_var=0.2 + 0.05 * (i % 3),
                presence_hours=7.0 + 0.2 * (i % 3),
                restless_frac=0.05 + 0.01 * (i % 3),
                onset=on,
                wake=on + timedelta(hours=7),
                midsleep=on + timedelta(hours=3.5),
                quality=0.9,
                valid=True,
                source_kind="synthetic",
            )
        )
    db.commit()


def _run(db: Session, kind: str, params: dict) -> runs.RunRecord:
    rec = runs.create_run(db, kind, params, [])
    return runs.execute(db, rec.id)


def _counts(db: Session) -> dict[str, int]:
    return {m.__tablename__: _count(db, m) for m in TABLES}


@pytest.fixture
def processed(db, data_dir, synth_dir):
    uid = make_user(db)
    _seed_history(db, uid)
    sess = ingest_session(db, uid, synth_dir)
    assert sess.usable and sess.source_kind.value == "synthetic"
    sid = sess.id
    rec = _run(db, "process_session", {"session_id": sid})
    assert rec.status is RunStatus.succeeded, rec.log
    return uid, sid, rec


def test_process_session_writes_windows(db, processed) -> None:
    uid, sid, rec = processed
    rows = db.scalars(select(WindowEstimateRow).where(WindowEstimateRow.session_id == sid)).all()
    assert rows and all(r.run_id == rec.id and r.user_id == uid for r in rows)
    valid = [r.rr_a for r in rows if r.rr_a is not None]
    assert len(valid) > len(rows) // 2
    assert all(abs(v - NIGHT_RR) <= 1.0 for v in valid)
    assert any(not r.presence for r in rows)  # the absent span
    hearts = db.scalars(select(HeartEstimateRow)).all()
    assert hearts and all(h.experimental and h.run_id == rec.id for h in hearts)
    assert f"nights={NIGHT.isoformat()}" in rec.log


def test_end_to_end_flag_and_idempotent_rerun(db, processed) -> None:
    uid, sid, _ = processed
    rec = _run(db, "run_nightly", {"user_id": uid, "day": NIGHT.isoformat()})
    assert rec.status is RunStatus.succeeded, rec.log

    nf = db.scalar(select(NightFeaturesRow).where(NightFeaturesRow.date == NIGHT))
    assert nf.valid and nf.run_id == rec.id and nf.source_kind == "synthetic"
    assert abs(nf.rr_med - NIGHT_RR) <= 1.0
    assert nf.session_ids == [sid]

    (flag,) = db.scalars(select(Flag).where(Flag.user_id == uid)).all()
    assert flag.date == NIGHT and flag.run_id == rec.id
    assert flag.phys_level == 1 and flag.state == "phys_only"
    assert flag.components["physiology"]["rr_med"]["z"] > 0

    # FR13: tonight is flagged, so the stored rr_med baseline excludes it.
    b = db.scalar(select(Baseline).where(Baseline.user_id == uid, Baseline.feature == "rr_med"))
    assert b.n == 6 and abs(b.median - 15.0) <= 0.5

    before = _counts(db)
    flag_id = flag.id
    assert _run(db, "process_session", {"session_id": sid}).status is RunStatus.succeeded
    rec2 = _run(db, "run_nightly", {"user_id": uid, "day": NIGHT.isoformat()})
    assert rec2.status is RunStatus.succeeded
    db.expire_all()
    assert _counts(db) == before  # re-run adds 0 rows
    flag2 = db.scalar(select(Flag).where(Flag.user_id == uid))
    assert flag2.id == flag_id and flag2.run_id == rec2.id  # updated in place
    assert db.scalar(select(func.count()).select_from(PipelineRun)) == 4


def test_band_alert_and_direction_from_indices(db, processed) -> None:
    uid, _, _ = processed

    def provider(_db, _uid, week):
        assert week == date(2026, 11, 9)  # Monday
        return {
            "phq2": {"value": 4.0, "direction": 1, "band": "positive screen", "band_alert": True},
            "who5": {"value": 80.0, "direction": -1, "band": "ok", "band_alert": False},
            "daily_pm.stress": {"value": 2.0, "band": None, "band_alert": False, "direction": None},
            "mystery": 3.0,  # no direction: skipped
        }

    out = fusion.run_nightly(db, uid, NIGHT, indices_provider=provider)
    db.commit()
    assert out["states"] == ["both"]
    flag = db.scalar(select(Flag).where(Flag.user_id == uid))
    m = flag.components["mental"]
    assert m["phq2"]["band"] == {"band": "positive screen", "source": "catalog"}
    assert m["mystery"]["skipped"] == "no_direction"
    assert m["daily_pm.stress"]["skipped"] == "no_direction"


def test_other_user_cannot_see_or_process(db, processed, data_dir) -> None:
    uid, sid, _ = processed
    other = make_user(db)
    out = fusion.run_nightly(db, other, NIGHT)
    assert out["windows"] == 0
    assert (
        db.scalar(
            select(func.count())
            .select_from(NightFeaturesRow)
            .where(NightFeaturesRow.user_id == other)
        )
        == 0
    )


def test_tampered_raw_file_fails_run(db, processed, data_dir) -> None:
    _, sid, _ = processed
    f = next((data_dir / "raw" / sid).glob("csi_*.csv.gz"))
    f.chmod(0o600)  # ingestion stores raw files read-only
    f.write_bytes(f.read_bytes() + b"x")
    before = _counts(db)
    rec = _run(db, "process_session", {"session_id": sid})
    assert rec.status is RunStatus.failed and "sha256" in rec.log
    assert _counts(db) == before  # rolled back, old estimates kept


def test_unusable_session_is_refused(db, processed) -> None:
    from backend.models import CaptureSession

    _, sid, _ = processed
    db.get(CaptureSession, sid).usable = False
    db.commit()
    before = _counts(db)
    rec = _run(db, "process_session", {"session_id": sid})
    assert rec.status is RunStatus.failed and "not usable" in rec.log
    assert _counts(db) == before


def test_latest_indices_looks_back_to_most_recent_week(db, processed) -> None:
    from csi_core.config import get_config

    uid, _, _ = processed
    seen = []

    def provider(_db, _uid, week):
        seen.append(week)
        return (
            {"phq2": {"value": 1.0, "band": None, "band_alert": False, "direction": 1}}
            if (week == date(2026, 11, 2))
            else {}
        )

    week, raw = fusion.latest_indices(db, uid, NIGHT, provider, get_config())
    assert week == date(2026, 11, 2) and "phq2" in raw
    assert seen == [date(2026, 11, 9), date(2026, 11, 2)]


def test_night_date_uses_profile_timezone() -> None:
    ny = ZoneInfo("America/New_York")
    ts = datetime(2026, 11, 11, 3, 0, tzinfo=UTC)  # 22:00 on the 10th in New York
    assert pipeline.night_date(ts, ny) == date(2026, 11, 10)
    assert pipeline.night_date(datetime(2026, 11, 11, 11, 0, tzinfo=UTC), ZoneInfo("UTC")) == (
        date(2026, 11, 10)
    )
    a, b = pipeline.night_bounds_utc(date(2026, 11, 10), ny)
    assert a == datetime(2026, 11, 10, 17, tzinfo=UTC) and b - a == timedelta(hours=24)


def test_raw_path_cannot_escape_data_dir(data_dir) -> None:
    with pytest.raises(ValueError):
        pipeline.resolve_raw_path("../outside.csv.gz", data_dir)


def test_missing_params_fail_clearly(db) -> None:
    for kind, msg in (("process_session", "session_id"), ("run_nightly", "user_id and day")):
        rec = _run(db, kind, {})
        assert rec.status is RunStatus.failed and msg in rec.log

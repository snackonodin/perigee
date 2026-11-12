"""INJ-1: device-side estimate batches. Property tests on random batches (hypothesis).

Properties: exact round-trip into the DB; a replay is a no-op; a malformed batch
writes nothing (no rows, no run, no archive); run_nightly works on injected data.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import (
    CaptureSession,
    HeartEstimateRow,
    NightFeaturesRow,
    PipelineRun,
    WindowEstimateRow,
)
from backend.services import injection, runs
from backend.services.injection import InjectionError, inject

from .conftest import make_user

CV = "team-scripts@abc1234"
PROPS = settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)

# ----------------------------------------------------------------- strategies

_t0 = st.datetimes(
    min_value=datetime(2026, 1, 1), max_value=datetime(2026, 12, 1), timezones=st.just(UTC)
)
_opt = lambda s: st.none() | s  # noqa: E731
_bpm = _opt(st.floats(0, 120, allow_nan=False))
_unit = st.floats(0, 1, allow_nan=False)


@st.composite
def batches(draw, min_windows: int = 1) -> dict:
    t0 = draw(_t0)
    offs = draw(st.lists(st.integers(0, 2000), min_size=min_windows, max_size=15, unique=True))
    windows = []
    for k in sorted(offs):
        a = t0 + timedelta(seconds=30 * k)
        windows.append(
            {
                "t_start": a.isoformat(),
                "t_end": (a + timedelta(seconds=60)).isoformat(),
                "rr_a": draw(_bpm),
                "rr_b": draw(_bpm),
                "pnr_db": draw(_opt(st.floats(-30, 60, allow_nan=False))),
                "motion_flag": draw(st.booleans()),
                "quality": draw(_unit),
                "presence": draw(st.booleans()),
            }
        )
    hearts = [
        {
            **{k: w[k] for k in ("t_start", "t_end")},
            "hr_bpm": draw(_opt(st.floats(20, 250, allow_nan=False))),
            "quality": draw(_unit),
        }
        for w in windows[: draw(st.integers(0, len(windows)))]
    ]
    motion = [
        {
            "t_start": w["t_start"],
            "t_end": w["t_end"],
            "motion": draw(st.booleans()),
            "score": draw(_opt(st.floats(0, 1e6, allow_nan=False))),
        }
        for w in windows
        if draw(st.booleans())
    ]
    return {
        "session": {"start_utc": windows[0]["t_start"], "end_utc": windows[-1]["t_end"]},
        "windows": windows,
        "hearts": hearts,
        "motion": motion,
    }


def _fixed_batch(n: int = 3) -> dict:
    """A small deterministic valid batch for example-based tests."""
    t0 = datetime(2026, 5, 1, 22, 0, tzinfo=UTC)
    ws = [
        {
            "t_start": (t0 + timedelta(seconds=30 * k)).isoformat(),
            "t_end": (t0 + timedelta(seconds=30 * k + 60)).isoformat(),
            "rr_a": 14.0 + k,
            "rr_b": 14.0 + k,
            "pnr_db": 8.0,
            "quality": 0.9,
        }
        for k in range(n)
    ]
    return {
        "session": {"start_utc": ws[0]["t_start"], "end_utc": ws[-1]["t_end"]},
        "windows": ws,
        "hearts": [],
        "motion": [],
    }


def _rows(db: Session, model, uid: str) -> list:
    db.expire_all()
    return db.scalars(select(model).where(model.user_id == uid).order_by(model.t_start)).all()


def _count(db: Session, model, uid: str) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model).where(model.user_id == uid))


# ----------------------------------------------------------------- properties


@PROPS
@given(batch=batches())
def test_round_trip_is_exact(db, data_dir, batch) -> None:
    uid = make_user(db)
    out = inject(db, uid, batch, CV)
    assert not out["duplicate"] and out["windows"] == len(batch["windows"])
    moving = {(m["t_start"], m["t_end"]): m["motion"] for m in batch["motion"]}
    rows = _rows(db, WindowEstimateRow, uid)
    assert len(rows) == len(batch["windows"])
    for r, w in zip(rows, batch["windows"], strict=True):
        assert r.t_start == datetime.fromisoformat(w["t_start"])
        assert r.t_end == datetime.fromisoformat(w["t_end"])
        assert (r.rr_a, r.rr_b, r.pnr_db, r.quality, r.presence) == (
            w["rr_a"],
            w["rr_b"],
            w["pnr_db"],
            w["quality"],
            w["presence"],
        )
        assert r.motion_flag == moving.get((w["t_start"], w["t_end"]), w["motion_flag"])
        assert r.session_id == out["session_id"] and r.run_id == out["run_id"]
    hearts = _rows(db, HeartEstimateRow, uid)
    assert [(h.hr_bpm, h.quality, h.experimental) for h in hearts] == [
        (h["hr_bpm"], h["quality"], True) for h in batch["hearts"]
    ]
    run = db.get(PipelineRun, out["run_id"])
    assert run.kind == "external_estimates" and run.user_id == uid
    assert run.code_version == CV and run.input_hashes == [out["batch_sha256"]]


@PROPS
@given(batch=batches())
def test_replay_is_a_noop(db, data_dir, batch) -> None:
    uid = make_user(db)
    first = inject(db, uid, batch, CV)
    before = [
        _count(db, m, uid)
        for m in (WindowEstimateRow, HeartEstimateRow, CaptureSession, PipelineRun)
    ]
    again = inject(db, uid, json.loads(json.dumps(batch)), "another-client-version")
    assert again["duplicate"] and again["run_id"] == first["run_id"]
    assert [
        _count(db, m, uid)
        for m in (WindowEstimateRow, HeartEstimateRow, CaptureSession, PipelineRun)
    ] == before


def _break(batch: dict, how: str) -> dict:
    b = json.loads(json.dumps(batch))
    w = b["windows"][0]
    if how == "rr_out_of_range":
        w["rr_a"] = 500.0
    elif how == "end_before_start":
        w["t_end"] = w["t_start"]
    elif how == "duplicate_window":
        b["windows"].append(dict(w))
    elif how == "heart_not_experimental":
        b["hearts"] = [{"t_start": w["t_start"], "t_end": w["t_end"], "experimental": False}]
    elif how == "naive_time":
        w["t_start"] = w["t_start"][:19]
    elif how == "unknown_field":
        w["surprise"] = 1
    elif how == "no_session":
        del b["session"]
    elif how == "motion_without_window":
        b["motion"] = [
            {
                "t_start": "2030-01-01T00:00:00+00:00",
                "t_end": "2030-01-01T00:01:00+00:00",
                "motion": True,
            }
        ]
    elif how == "quality_above_one":
        w["quality"] = 1.5
    return b


BREAKS = [
    "rr_out_of_range",
    "end_before_start",
    "duplicate_window",
    "heart_not_experimental",
    "naive_time",
    "unknown_field",
    "no_session",
    "motion_without_window",
    "quality_above_one",
]


@PROPS
@given(batch=batches(), how=st.sampled_from(BREAKS))
def test_malformed_batch_writes_nothing(db, data_dir, batch, how) -> None:
    uid = make_user(db)
    with pytest.raises(InjectionError):
        inject(db, uid, _break(batch, how), CV)
    for model in (WindowEstimateRow, HeartEstimateRow, CaptureSession, PipelineRun):
        assert _count(db, model, uid) == 0
    raw = data_dir / "raw"
    assert not raw.exists() or not any(raw.iterdir())


def test_code_version_is_required(db, data_dir) -> None:
    uid = make_user(db)
    batch = _fixed_batch()
    for bad in (None, "", "x" * 65):
        with pytest.raises(InjectionError, match="X-Code-Version"):
            inject(db, uid, batch, bad)
    assert _count(db, PipelineRun, uid) == 0


def test_other_users_session_is_invisible(db, data_dir) -> None:
    a, b = make_user(db), make_user(db)
    out = inject(db, a, _fixed_batch(), CV)
    with pytest.raises(InjectionError, match="session not found"):
        inject(
            db,
            b,
            {
                "session_id": out["session_id"],
                "windows": [
                    {"t_start": "2026-05-01T00:00:00+00:00", "t_end": "2026-05-01T00:01:00+00:00"}
                ],
            },
            CV,
        )
    assert _count(db, WindowEstimateRow, b) == 0 and _count(db, PipelineRun, b) == 0


def test_batch_for_existing_session_replaces_its_estimates(db, data_dir) -> None:
    uid = make_user(db)
    first = inject(db, uid, _fixed_batch(3), CV)
    sid = first["session_id"]
    w = {
        "t_start": "2026-06-01T23:00:00+00:00",
        "t_end": "2026-06-01T23:01:00+00:00",
        "rr_a": 14.0,
        "rr_b": 14.0,
    }
    second = inject(db, uid, {"session_id": sid, "windows": [w]}, CV)
    assert second["session_id"] == sid and not second["duplicate"]
    assert [r.rr_a for r in _rows(db, WindowEstimateRow, uid)] == [14.0]


def test_run_nightly_on_injected_night(db, data_dir) -> None:
    uid = make_user(db)
    onset = datetime(2026, 11, 3, 23, 0, tzinfo=UTC)
    windows = [
        {
            "t_start": (onset + timedelta(seconds=30 * k)).isoformat(),
            "t_end": (onset + timedelta(seconds=30 * k + 60)).isoformat(),
            "rr_a": 14.0 + (k % 5) * 0.1,
            "rr_b": 14.0,
            "pnr_db": 9.0,
            "quality": 0.9,
        }
        for k in range(int(7 * 3600 / 30))
    ]
    out = inject(
        db,
        uid,
        {
            "session": {"start_utc": windows[0]["t_start"], "end_utc": windows[-1]["t_end"]},
            "windows": windows,
        },
        CV,
    )
    rec = runs.execute(
        db,
        runs.create_run(
            db, "run_nightly", {"user_id": uid, "day": "2026-11-03"}, [], user_id=uid
        ).id,
    )
    assert rec.status.value == "succeeded", rec.log
    nf = db.scalar(select(NightFeaturesRow).where(NightFeaturesRow.user_id == uid))
    assert nf.date == date(2026, 11, 3) and nf.valid and nf.session_ids == [out["session_id"]]
    assert nf.rr_med == pytest.approx(14.2) and nf.source_kind == "csi"


def test_csv_and_cli(db, data_dir, tmp_path, capsys) -> None:
    from tools import cli

    uid = make_user(db)
    rows = [
        "kind,t_start,t_end,rr_a,rr_b,quality,hr_bpm,motion,score",
        "window,2026-05-01T00:00:00+00:00,2026-05-01T00:01:00+00:00,14,14.5,0.8,,,",
        "window,2026-05-01T00:00:30+00:00,2026-05-01T00:01:30+00:00,,,0,,,",
        "heart,2026-05-01T00:00:00+00:00,2026-05-01T00:01:00+00:00,,,0.3,61,,",
        "motion,2026-05-01T00:00:30+00:00,2026-05-01T00:01:30+00:00,,,,,true,42",
    ]
    f = tmp_path / "estimates.csv"
    f.write_text("\n".join(rows) + "\n")
    args = cli.build_parser().parse_args(
        ["ingest-estimates", str(f), "--user", uid, "--code-version", CV]
    )
    assert cli.cmd_ingest_estimates(db, args) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["windows"], out["hearts"], out["motion"]) == (2, 1, 1)
    ws = _rows(db, WindowEstimateRow, uid)
    assert [(w.rr_a, w.motion_flag) for w in ws] == [(14.0, False), (None, True)]
    assert cli.cmd_ingest_estimates(db, args) == 0  # replay
    assert json.loads(capsys.readouterr().out)["duplicate"] is True


def test_api_endpoint(db, data_dir) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api.v1 import ingest
    from backend.errors import install_error_handlers
    from backend.services import accounts

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(ingest.router)
    client = TestClient(app)
    tok = accounts.signup(db, "dev@example.test", "a-long-test-password-123").access_token
    body = _fixed_batch()
    h = {"Authorization": f"Bearer {tok}", "X-Code-Version": CV}
    r1 = client.post("/api/v1/ingest/estimates", json=body, headers=h)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/api/v1/ingest/estimates", json=body, headers=h)
    assert r2.status_code == 200 and r2.json()["duplicate"] is True
    assert (
        client.post(
            "/api/v1/ingest/estimates", json=_break(body, "rr_out_of_range"), headers=h
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/ingest/estimates", json=body, headers={"Authorization": f"Bearer {tok}"}
        ).status_code
        == 422
    )
    assert client.post("/api/v1/ingest/estimates", json=body).status_code == 401
    assert injection.KIND in runs.registered_kinds()

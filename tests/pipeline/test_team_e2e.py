"""Integration (SCR-1 item 3): real-format capture -> DB, through the team cores.

Anonymised fixtures -> plugins.team_capture (our capture folder) -> ingest_session ->
process_session (team breath/motion via the matrix seam, team I/Q heart) ->
run_nightly, all through the runs registry with provenance.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.models import (
    CaptureSession,
    HeartEstimateRow,
    NightFeaturesRow,
    PipelineRun,
    WindowEstimateRow,
)
from backend.schemas.contracts import RunStatus
from backend.services import fusion, pipeline, runs
from backend.services.ingestion import ingest_session
from csi_core.breath import estimate_windows
from csi_core.config import get_config
from csi_core.load import read_rotating
from csi_core.preprocess import clean
from plugins.team_capture import to_capture_folder

from .conftest import make_user

pytestmark = pytest.mark.slow

FIX = Path(__file__).resolve().parents[1] / "fixtures"
NIGHT = date(2027, 1, 14)  # fixtures are shifted to epoch 1.8e9 = 2027-01-15 08:00 UTC


@pytest.fixture
def team_cfg(monkeypatch):
    cfg = get_config()
    est = cfg.estimators.model_copy(
        update={
            "breath": "plugins.team_breath:breath_core_matrix",
            "breath_input": "matrix",
            "motion": "plugins.team_motion:motion_core_matrix",
            "motion_input": "matrix",
            "heart": "plugins.team_heart:heart_core_iq",
            "heart_input": "iq",
        }
    )
    br = cfg.breath.model_copy(update={"window_s": 15.0, "step_s": 15.0})
    cfg = cfg.model_copy(update={"estimators": est, "breath": br})
    monkeypatch.setattr(pipeline, "get_config", lambda: cfg)  # what the run handlers read
    monkeypatch.setattr(fusion, "get_config", lambda: cfg)
    return cfg


def _run(db, kind, params, uid):
    rec = runs.execute(db, runs.create_run(db, kind, params, [], user_id=uid).id)
    assert rec.status is RunStatus.succeeded, rec.log
    return rec


@pytest.mark.parametrize("name", ["team_empty_40s.csv", "team_iq_empty_30s.csv"])
def test_real_format_capture_end_to_end(db, data_dir, tmp_path, team_cfg, name) -> None:
    uid = make_user(db)
    folder = to_capture_folder(FIX / name, tmp_path / "capture")
    meta = (folder / "meta.json").read_text()
    assert "mac" not in meta and 'room_notes": null' in meta

    sess = ingest_session(db, uid, folder)
    assert sess.usable and sess.source_kind.value == "csi"
    row = db.get(CaptureSession, sess.id)
    assert row.mean_rows_per_s > team_cfg.capture.min_rows_per_s

    rec = _run(db, "process_session", {"session_id": sess.id}, uid)
    win = db.scalars(
        select(WindowEstimateRow)
        .where(WindowEstimateRow.session_id == sess.id)
        .order_by(WindowEstimateRow.t_start)
    ).all()
    direct = estimate_windows(clean(read_rotating([FIX / name]), team_cfg), sess.id, team_cfg)
    assert len(win) == len(direct) >= 2
    for r, d in zip(win, direct, strict=True):  # DB rows == team cores applied directly
        assert (r.pnr_db, r.rr_a, r.motion_flag, r.presence) == pytest.approx(
            (d.pnr_db, d.rr_a, d.motion_flag, d.presence)
        ) or (r.rr_a is None and d.rr_a is None)
        assert r.run_id == rec.id and r.user_id == uid

    hearts = db.scalars(
        select(HeartEstimateRow).where(HeartEstimateRow.session_id == sess.id)
    ).all()
    if "iq" in name:
        assert hearts and all(h.experimental for h in hearts)
        assert any(h.hr_bpm is not None for h in hearts)
    else:
        assert hearts == []  # amplitude-only capture: the I/Q heart core has nothing to use

    nightly = _run(db, "run_nightly", {"user_id": uid, "day": NIGHT.isoformat()}, uid)
    nf = db.scalar(select(NightFeaturesRow).where(NightFeaturesRow.user_id == uid))
    assert nf is not None and nf.date == NIGHT and nf.session_ids == [sess.id]
    assert nf.source_kind == "csi" and nf.run_id == nightly.id
    assert not nf.valid  # seconds of data, far below night.min_valid_hours
    assert db.get(PipelineRun, rec.id).user_id == uid

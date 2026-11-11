"""SCR-1 golden test: team plug-ins reproduce the vendored team code on a real capture.

Fixture: a 40 s anonymised slice of the team's empty-room capture (no person; MAC
zeroed; raw_line/session_id dropped; clocks shifted). The vendored score_windows is
the reference: our reader + bin_average + adapters must give the same per-window
rate A, rate B, PNR and motion feature.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from csi_core.breath import estimate_windows
from csi_core.config import get_config, resolve_estimator
from csi_core.load import read_rotating
from csi_core.preprocess import clean
from csi_core.windows import window_slices
from plugins import team_breath, team_heart, team_motion
from plugins.vendor.waiwai1 import pipeline as wp

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "team_empty_40s.csv"
WINDOW_S = 20.0  # two non-overlapping windows in the 40 s slice


@pytest.fixture(scope="module")
def team_cfg():
    cfg = get_config()
    est = cfg.estimators.model_copy(
        update={
            "breath": "plugins.team_breath:breath_core_matrix",
            "breath_input": "matrix",
            "motion": "plugins.team_motion:motion_core_matrix",
            "motion_input": "matrix",
            "heart": "plugins.team_heart:heart_core",
        }
    )
    br = cfg.breath.model_copy(update={"window_s": WINDOW_S, "step_s": WINDOW_S})
    return cfg.model_copy(update={"estimators": est, "breath": br})


@pytest.fixture(scope="module")
def reference() -> list[dict]:
    capture = wp.load_capture(FIXTURE)
    settings = {"resample_rate_hz": 20, "window_s": WINDOW_S, "hop_s": WINDOW_S}
    return wp.score_windows(capture, settings)


@pytest.fixture(scope="module")
def sig(team_cfg):
    return clean(read_rotating([FIXTURE]), team_cfg)


def test_specs_resolve_to_adapters(team_cfg) -> None:
    assert resolve_estimator(team_cfg.estimators.breath) is team_breath.breath_core_matrix
    assert resolve_estimator(team_cfg.estimators.motion) is team_motion.motion_core_matrix


def test_matrix_matches_team_resampling(sig) -> None:
    capture = wp.load_capture(FIXTURE)
    _, theirs, _ = wp.resample_packets(capture, 20.0)
    n = sig.amps.shape[0]
    np.testing.assert_allclose(sig.amps, theirs[:n][:, capture.active_mask], rtol=0, atol=1e-12)


def test_golden_breath_and_motion_match_score_windows(sig, team_cfg, reference) -> None:
    slices = window_slices(sig, WINDOW_S, WINDOW_S)
    assert len(slices) == len(reference) == 2
    for s, ref in zip(slices, reference, strict=True):
        a, b, pnr = team_breath.breath_core_matrix(sig.amps[s], sig.active, sig.fs, team_cfg)
        assert a == pytest.approx(ref["rate_A"], abs=1e-9)
        assert (b is None and ref["rate_B"] is None) or b == pytest.approx(ref["rate_B"], abs=1e-9)
        assert pnr == pytest.approx(ref["pnr_db"], abs=1e-9)
        _, score = team_motion.motion_core_matrix(sig.amps[s], sig.active, sig.fs, team_cfg, a)
        assert score == pytest.approx(ref["motion_feature"], rel=1e-9)


def test_end_to_end_window_estimates_with_team_cores(sig, team_cfg, reference) -> None:
    ws = estimate_windows(sig, "s", team_cfg)
    assert [w.pnr_db for w in ws] == pytest.approx([r["pnr_db"] for r in reference], abs=1e-9)
    assert all(w.t_start.tzinfo is not None for w in ws)


def test_team_heart_declines_amplitude_input(sig, team_cfg) -> None:
    assert team_heart.heart_core(sig.x[:400], sig.fs, team_cfg) == (None, 0.0)


def test_signal_fallback_uses_team_estimators(sig, team_cfg) -> None:
    a, b, pnr = team_breath.breath_core(sig.x[:400], sig.fs, team_cfg)
    ra, rp = wp.spectral_rate(sig.x[:400], sig.fs)
    assert (a, pnr) == (ra, rp) and b == wp.time_domain_rate(sig.x[:400], sig.fs)

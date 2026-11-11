"""SCR-2 golden test: the team's I/Q heart pipeline through our reader and seam.

Fixture: a whole 30 s anonymised empty-room I/Q capture (no person; MAC zeroed;
raw_line/session_id dropped; clocks shifted). Reference = the vendored
heart_rate.load_iq_capture / analyze_capture on the same file. Heart output is
experimental only (FR8); an empty room still yields numbers, as the team documents.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from csi_core.config import get_config
from csi_core.heart import estimate_session, estimate_windows_iq
from csi_core.load import read_rotating
from csi_core.preprocess import has_iq, iq_packets
from plugins import team_heart
from plugins.vendor.waiwai1 import heart_rate as hr_mod

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "team_iq_empty_30s.csv"
WINDOW_S = 15.0  # two windows >= 12 s (the team minimum) in the 30 s capture


@pytest.fixture(scope="module")
def iq_cfg():
    cfg = get_config()
    est = cfg.estimators.model_copy(
        update={"heart": "plugins.team_heart:heart_core_iq", "heart_input": "iq"}
    )
    br = cfg.breath.model_copy(update={"window_s": WINDOW_S, "step_s": WINDOW_S})
    return cfg.model_copy(update={"estimators": est, "breath": br})


@pytest.fixture(scope="module")
def df():
    return read_rotating([FIXTURE])


def test_reader_keeps_iq(df) -> None:
    assert has_iq(df) and "i63" in df.columns and "q63" in df.columns


def test_iq_packets_match_team_loader(df, iq_cfg) -> None:
    times, csi, mask, _, _ = hr_mod.load_iq_capture(FIXTURE)
    pk = iq_packets(df, iq_cfg)
    np.testing.assert_allclose(pk.t_s, times, rtol=0, atol=1e-9)
    np.testing.assert_array_equal(pk.csi, csi)
    np.testing.assert_array_equal(pk.active, mask)


def test_golden_heart_windows_match_analyze_capture(df, iq_cfg) -> None:
    ref = hr_mod.analyze_capture(FIXTURE, window_s=WINDOW_S)["windows"]
    pk = iq_packets(df, iq_cfg)
    ours = estimate_windows_iq(pk, "s", iq_cfg)
    analysable = [e for e in ours if e.hr_bpm is not None]
    assert len(analysable) == len(ref) >= 1
    for k, (e, r) in enumerate(zip(analysable, ref, strict=True)):
        assert e.hr_bpm == pytest.approx(r["spectral_rate_bpm"], abs=1e-9)
        assert e.experimental is True
        sel = (pk.t_s >= k * WINDOW_S) & (pk.t_s < (k + 1) * WINDOW_S)  # their selection
        assert pk.t_s[sel][0] == pytest.approx(r["start_s"], abs=1e-6)
        mine = hr_mod.analyze_window(pk.t_s[sel], pk.csi[sel], pk.active)
        # Equal up to float rounding of the time base (team: us/1e6 then subtract t0;
        # ours: subtract t0 in us then /1e6), which moves results by ~1e-9.
        for k in ("spectral_rate_bpm", "peak_interval_rate_bpm", "peak_to_median_psd_db"):
            assert (mine[k] is None and r[k] is None) or mine[k] == pytest.approx(r[k], rel=1e-6)


def test_short_window_gets_no_estimate(iq_cfg, df) -> None:
    pk = iq_packets(df, iq_cfg)
    sel = pk.t_s < 5.0  # < 12 s: the team code refuses
    with pytest.raises(ValueError):
        team_heart.heart_core_iq(pk.t_s[sel], pk.csi[sel], pk.active, iq_cfg)


def test_iq_mode_on_amplitude_capture_is_empty(iq_cfg) -> None:
    amp_only = read_rotating([FIXTURE.parent / "team_empty_40s.csv"])
    assert not has_iq(amp_only)
    assert estimate_session(amp_only, "s", iq_cfg) == []

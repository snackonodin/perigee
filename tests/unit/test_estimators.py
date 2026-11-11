"""Golden tests for the estimator seams. A replacement core must keep these green."""

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from csi_core import breath, heart, motion
from csi_core.config import resolve_estimator
from csi_core.load import read_rotating
from csi_core.preprocess import CleanSignal, clean

from .conftest import RR

PLUG = "tests.unit.dummy_plugins"


@pytest.fixture(scope="module")
def sig(night_dir, cfg) -> CleanSignal:
    _, paths = night_dir
    return clean(read_rotating([p for p in paths if p.name.startswith("csi_")]), cfg)


@pytest.fixture(scope="module")
def windows(sig, cfg):
    return breath.estimate_windows(sig, "sess", cfg)


def _marker_spans(night_dir, label):
    d, _ = night_dir
    mk = pd.read_csv(d / "markers.csv")
    mk["t"] = pd.to_datetime(mk["host_time_utc"], utc=True)
    a = mk.loc[mk["label"] == f"{label}_start", "t"].tolist()
    b = mk.loc[mk["label"] == f"{label}_end", "t"].tolist()
    return list(zip(a, b, strict=True))


def test_clean_signal_shape(sig, cfg) -> None:
    assert sig.fs == cfg.preprocess.resample_hz
    assert sig.x.shape == sig.t_s.shape
    assert sig.t0_utc.tzinfo is not None
    assert sig.t_s[-1] == pytest.approx(600, abs=1)


def _swap(cfg, **specs):
    return cfg.model_copy(update={"estimators": cfg.estimators.model_copy(update=specs)})


def test_golden_rr_recovered(windows, cfg) -> None:
    valid = [w for w in windows if w.rr_a is not None]
    assert len(valid) >= 0.6 * len(windows)
    for w in valid:
        assert abs(w.rr_a - RR) <= 1.0  # primary estimator: done criterion
        assert abs(w.rr_b - RR) <= cfg.breath.max_estimator_disagreement_bpm
    assert np.median([w.rr_a for w in valid]) == pytest.approx(RR, abs=0.2)
    assert np.median([w.rr_b for w in valid]) == pytest.approx(RR, abs=1.0)


def test_golden_motion_matches_markers(windows, night_dir) -> None:
    spans = _marker_spans(night_dir, "motion")
    for w in windows:
        overlaps = any(w.t_start < b and a < w.t_end for a, b in spans)
        if w.motion_flag:
            assert overlaps
            assert w.rr_a is None
    assert any(w.motion_flag for w in windows)


def test_absent_windows_have_no_rr(windows, night_dir) -> None:
    ((a, b),) = _marker_spans(night_dir, "absent")
    inside = [w for w in windows if w.t_start >= a and w.t_end <= b]
    assert all(w.rr_a is None for w in inside)


def test_default_specs_are_reference_cores(cfg) -> None:
    assert resolve_estimator(cfg.estimators.breath) is breath.reference_core
    assert resolve_estimator(cfg.estimators.heart) is heart.reference_core
    assert resolve_estimator(cfg.estimators.motion) is motion.reference_core


def test_plugin_spec_swaps_numbers_only(sig, cfg, windows) -> None:
    swapped = _swap(cfg, breath=f"{PLUG}:breath_core")
    out = breath.estimate_windows(sig, "sess", swapped)
    assert len(out) == len(windows)
    for a, b in zip(windows, out, strict=True):
        assert (a.t_start, a.t_end, a.motion_flag, a.presence) == (
            b.t_start,
            b.t_end,
            b.motion_flag,
            b.presence,
        )
        if b.presence and not b.motion_flag:
            assert (b.rr_a, b.rr_b, b.pnr_db) == (12.0, 12.5, 30.0)


def test_disagreeing_plugin_is_rejected(sig, cfg) -> None:
    out = breath.estimate_windows(sig, "s", _swap(cfg, breath=f"{PLUG}:breath_core_disagree"))
    assert all(w.rr_a is None for w in out)


def test_motion_plugin_swap(sig, cfg, windows) -> None:
    out = breath.estimate_windows(sig, "s", _swap(cfg, motion=f"{PLUG}:motion_never"))
    assert not any(w.motion_flag for w in out)
    assert sum(w.rr_a is not None for w in out) >= sum(w.rr_a is not None for w in windows)


def test_heart_plugin_swap(cfg) -> None:
    s = _sine(1.0)
    est = heart.estimate_windows(s, "s", _swap(cfg, heart=f"{PLUG}:heart_core"))
    assert est and all(e.hr_bpm == 61.0 and e.quality == 0.4 for e in est)


def test_motion_detect_presence_and_motion(cfg) -> None:
    rng = np.random.default_rng(0)
    segs = [rng.normal(0, 1, 200) for _ in range(10)]
    segs[3] = segs[3] * 100  # whole-window burst: session-level outlier
    segs[5][100:120] *= 100  # 1-s burst inside a window still stands out
    segs[7] = np.zeros(200)
    r = motion.detect(segs, 20.0, cfg)
    assert r.motion[3] and r.motion[5]
    assert r.motion.sum() == 2
    assert not r.presence[7] and r.presence.sum() == 9


def _sine(hz: float, fs: float = 20.0) -> CleanSignal:
    t = np.arange(0, 300, 1 / fs)
    rng = np.random.default_rng(1)
    x = np.sin(2 * np.pi * hz * t) + rng.normal(0, 0.2, t.size)
    return CleanSignal(t_s=t, x=x, fs=fs, t0_utc=datetime(2026, 1, 1, tzinfo=UTC))


def test_heart_reference_on_sine(cfg) -> None:
    est = heart.estimate_windows(_sine(1.2, cfg.preprocess.resample_hz), "s", cfg)
    assert est and all(e.experimental for e in est)
    assert all(abs(e.hr_bpm - 72.0) <= 1.0 for e in est)

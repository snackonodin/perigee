"""Team heart-rate pipeline (waiwai1 heart_rate.py) as csi_core plug-ins.

Experimental only (FR8): stored, never fused. Use with config.yaml:
    estimators:
      heart: "plugins.team_heart:heart_core_iq"
      heart_input: iq

heart_core_iq needs signed I/Q captures (ESP-B firmware). heart_core (signal input)
returns no estimate: phase is not recoverable from amplitudes, so the team method
cannot run there and no number is invented.
"""

from __future__ import annotations

import numpy as np

from plugins.vendor.waiwai1 import heart_rate as hr_mod


def heart_core(x: np.ndarray, fs: float, cfg) -> tuple[float | None, float]:
    return None, 0.0


def heart_core_iq(
    t_s: np.ndarray, csi: np.ndarray, active: np.ndarray, cfg
) -> tuple[float | None, float]:
    """The team's five-stage I/Q pipeline (heart_rate.analyze_window) on one window.

    hr = the spectral estimate. quality is 1 only when the spectral and peak-interval
    estimates agree within breath.max_estimator_disagreement_bpm and the PSD peak
    clears breath.min_pnr_db (heart reuses the breath gates until validated), else 0.
    Raises ValueError for windows the team code cannot analyse (< 12 s, low rate).
    """
    r = hr_mod.analyze_window(t_s, csi, active)
    spectral, peaks = r["spectral_rate_bpm"], r["peak_interval_rate_bpm"]
    agree = peaks is not None and abs(spectral - peaks) <= cfg.breath.max_estimator_disagreement_bpm
    ok = agree and r["peak_to_median_psd_db"] >= cfg.breath.min_pnr_db
    return float(spectral), 1.0 if ok else 0.0

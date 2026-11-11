"""Experimental heart-rate estimates (FR8). Stored only, never used by fusion.

Plug-in seam: ``config.yaml estimators.heart`` names a
``heart_core(x, fs, cfg) -> (hr_bpm, quality)`` for one window of the heart-band
clean signal. Windowing and the HeartEstimate output stay here.

Reference core: Welch peak in ``preprocess.heart_band_hz``; quality 1 when the
peak clears ``breath.min_pnr_db`` (reused until a heart value is validated), else 0.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.schemas.contracts import HeartEstimate
from csi_core.config import CoreConfig, resolve_estimator
from csi_core.preprocess import CleanSignal, clean_band
from csi_core.windows import spectral_peak, window_slices, window_times


def reference_core(x: np.ndarray, fs: float, cfg: CoreConfig) -> tuple[float | None, float]:
    f, pnr_db = spectral_peak(x, fs, cfg.preprocess.heart_band_hz)
    if f is None or pnr_db is None or pnr_db < cfg.breath.min_pnr_db:
        return None, 0.0
    return 60.0 * f, 1.0


def clean_heart(df: pd.DataFrame, cfg: CoreConfig) -> CleanSignal:
    return clean_band(df, cfg, cfg.preprocess.heart_band_hz)


def estimate_windows(sig: CleanSignal, session_id: str, cfg: CoreConfig) -> list[HeartEstimate]:
    core = resolve_estimator(cfg.estimators.heart)
    out: list[HeartEstimate] = []
    for s in window_slices(sig, cfg.breath.window_s, cfg.breath.step_s):
        t_a, t_b = window_times(sig, s)
        hr, q = core(sig.x[s], sig.fs, cfg)
        ok = hr is not None and np.isfinite(hr) and 20 <= hr <= 250
        out.append(
            HeartEstimate(
                session_id=session_id,
                t_start=t_a,
                t_end=t_b,
                hr_bpm=float(hr) if ok else None,
                quality=float(np.clip(q, 0.0, 1.0)) if ok else 0.0,
            )
        )
    return out

"""Experimental heart-rate estimates (FR8). Stored only, never used by fusion.

Plug-in seam: ``config.yaml estimators.heart`` names a
``heart_core(x, fs, cfg) -> (hr_bpm, quality)`` for one window of the heart-band
clean signal. Windowing and the HeartEstimate output stay here.

Reference core: Welch peak in ``preprocess.heart_band_hz``; quality 1 when the
peak clears ``breath.min_pnr_db`` (reused until a heart value is validated), else 0.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from backend.schemas.contracts import HeartEstimate
from csi_core.config import CoreConfig, resolve_estimator
from csi_core.preprocess import CleanSignal, IQPackets, clean_band, has_iq, iq_packets
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


def _estimate(session_id: str, t_a, t_b, hr, q) -> HeartEstimate:
    ok = hr is not None and np.isfinite(hr) and 20 <= hr <= 250
    return HeartEstimate(
        session_id=session_id,
        t_start=t_a,
        t_end=t_b,
        hr_bpm=float(hr) if ok else None,
        quality=float(np.clip(q, 0.0, 1.0)) if ok else 0.0,
    )


def estimate_windows_iq(pk: IQPackets, session_id: str, cfg: CoreConfig) -> list[HeartEstimate]:
    """``estimators.heart_input: iq``: ``heart_core_iq(t_s, csi, active, cfg) -> (hr, q)``
    on each window's packets (window_s / step_s on the device clock from the first packet).
    A core that cannot analyse a window raises ValueError; that window gets no estimate."""
    core = resolve_estimator(cfg.estimators.heart)
    win, step = cfg.breath.window_s, cfg.breath.step_s
    out: list[HeartEstimate] = []
    start = 0.0
    while start < pk.t_s[-1]:
        sel = (pk.t_s >= start) & (pk.t_s < start + win)
        if sel.sum() >= 2:
            t = pk.t_s[sel]
            try:
                hr, q = core(t, pk.csi[sel], pk.active, cfg)
            except ValueError:
                hr, q = None, 0.0
            out.append(
                _estimate(
                    session_id,
                    pk.t0_utc + timedelta(seconds=float(t[0])),
                    pk.t0_utc + timedelta(seconds=float(t[-1]) + 1e-3),
                    hr,
                    q,
                )
            )
        start += step
    return out


def estimate_session(df: pd.DataFrame, session_id: str, cfg: CoreConfig) -> list[HeartEstimate]:
    """Heart estimates for one capture, dispatching on ``estimators.heart_input``.
    With "iq" and an amplitude-only capture there is nothing to estimate: []."""
    if cfg.estimators.heart_input == "iq":
        return estimate_windows_iq(iq_packets(df, cfg), session_id, cfg) if has_iq(df) else []
    return estimate_windows(clean_heart(df, cfg), session_id, cfg)

"""Window-level breathing-rate estimates (FR6).

Plug-in seam: ``config.yaml estimators.breath`` names a
``breath_core(x, fs, cfg) -> (rr_a, rr_b, pnr_db)`` for one window of the clean
signal (None = no estimate). Windowing, gating, quality, presence and the
WindowEstimate output stay here, so a swapped core changes numbers only.

Reference core: rr_a = Welch spectral peak in the breathing band, rr_b = peak
count with a minimum spacing set by the band's upper edge, PNR in dB.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from backend.schemas.contracts import WindowEstimate
from csi_core import motion
from csi_core.config import CoreConfig, resolve_estimator
from csi_core.preprocess import CleanSignal
from csi_core.windows import spectral_peak, window_slices, window_times


def reference_core(
    x: np.ndarray, fs: float, cfg: CoreConfig
) -> tuple[float | None, float | None, float | None]:
    band = cfg.preprocess.breath_band_hz
    f, pnr_db = spectral_peak(x, fs, band)
    rr_a = None if f is None else 60.0 * f
    peaks, _ = find_peaks(x - np.median(x), height=0.0, distance=max(int(fs / band[1]), 1))
    rr_b = None
    if peaks.size >= 2:
        rr_b = 60.0 * (peaks.size - 1) / ((peaks[-1] - peaks[0]) / fs)
    return rr_a, rr_b, pnr_db


def _quality(
    pnr_ok: bool, rr_a: float | None, rr_b: float | None, moving: bool, cfg: CoreConfig
) -> float:
    """Mean of three equally weighted checks: clear peak, estimator agreement, no motion."""
    if rr_a is None or rr_b is None:
        agree = 0.0
    else:
        agree = max(0.0, 1.0 - abs(rr_a - rr_b) / cfg.breath.max_estimator_disagreement_bpm)
    return float(np.clip((float(pnr_ok) + agree + float(not moving)) / 3.0, 0.0, 1.0))


def _bpm(v: float | None) -> float | None:
    if v is None or not np.isfinite(v) or not 0 <= v <= 120:
        return None
    return float(v)


def estimate_windows(sig: CleanSignal, session_id: str, cfg: CoreConfig) -> list[WindowEstimate]:
    """One WindowEstimate per window. rr_a/rr_b are None when the window is
    absent, moving, has no clear peak, or the two estimators disagree."""
    core = resolve_estimator(cfg.estimators.breath)
    slices = window_slices(sig, cfg.breath.window_s, cfg.breath.step_s)
    segs = [sig.x[s] for s in slices]
    mr = motion.detect(segs, sig.fs, cfg)
    out: list[WindowEstimate] = []
    for k, (s, seg) in enumerate(zip(slices, segs, strict=True)):
        t_a, t_b = window_times(sig, s)
        present, moving = bool(mr.presence[k]), bool(mr.motion[k])
        rr_a, rr_b, pnr = core(seg, sig.fs, cfg)
        rr_a, rr_b = _bpm(rr_a), _bpm(rr_b)
        pnr = None if pnr is None or not np.isfinite(pnr) else float(pnr)
        pnr_ok = pnr is not None and pnr >= cfg.breath.min_pnr_db
        q = _quality(pnr_ok, rr_a, rr_b, moving, cfg) if present else 0.0
        agree = (
            rr_a is not None
            and rr_b is not None
            and abs(rr_a - rr_b) <= cfg.breath.max_estimator_disagreement_bpm
        )
        if not (present and not moving and pnr_ok and agree):
            rr_a = rr_b = None
        out.append(
            WindowEstimate(
                session_id=session_id,
                t_start=t_a,
                t_end=t_b,
                rr_a=rr_a,
                rr_b=rr_b,
                pnr_db=pnr,
                motion_flag=moving,
                quality=q,
                presence=present,
            )
        )
    return out

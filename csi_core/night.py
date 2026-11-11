"""Nightly features (FR7) and personal baselines (FR13)."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np

from backend.schemas.contracts import BaselineState, Maturity, NightFeatures, WindowEstimate
from csi_core.config import CoreConfig

MAD_SCALE = 1.4826  # MAD -> standard deviation for Gaussian data


def _union_seconds(spans: list[tuple[datetime, datetime]]) -> float:
    total = 0.0
    cur_a: datetime | None = None
    cur_b: datetime | None = None
    for a, b in sorted(spans):
        if cur_b is None or a > cur_b:
            if cur_a is not None and cur_b is not None:
                total += (cur_b - cur_a).total_seconds()
            cur_a, cur_b = a, b
        elif b > cur_b:
            cur_b = b
    if cur_a is not None and cur_b is not None:
        total += (cur_b - cur_a).total_seconds()
    return total


def aggregate(
    user_id: str, night: date, windows: list[WindowEstimate], cfg: CoreConfig
) -> NightFeatures:
    """Summarise one night's windows.

    presence_hours: union of present windows (overlaps counted once).
    restless_frac: share of present windows flagged as motion.
    rr_med / rr_var: median / variance of accepted rr_a values (rr_var needs >= 2).
    onset / wake: first / last present window; midsleep halfway between.
    quality: mean window quality over present windows.
    valid: enough presence hours, enough quality, and an rr_med.
    """
    ws = sorted(windows, key=lambda w: w.t_start)
    present = [w for w in ws if w.presence]
    session_ids = list(dict.fromkeys(w.session_id for w in ws))
    if not present:
        return NightFeatures(
            user_id=user_id, date=night, presence_hours=0.0, session_ids=session_ids
        )
    hours = min(_union_seconds([(w.t_start, w.t_end) for w in present]) / 3600.0, 24.0)
    restless = sum(w.motion_flag for w in present) / len(present)
    rr = np.array([w.rr_a for w in present if w.rr_a is not None], dtype=float)
    rr_med = float(np.median(rr)) if rr.size else None
    rr_var = float(np.var(rr)) if rr.size >= 2 else None
    onset = present[0].t_start
    wake = max(w.t_end for w in present)
    quality = float(np.mean([w.quality for w in present]))
    valid = (
        hours >= cfg.night.min_valid_hours
        and quality >= cfg.night.min_quality
        and rr_med is not None
    )
    return NightFeatures(
        user_id=user_id,
        date=night,
        rr_med=rr_med,
        rr_var=rr_var,
        presence_hours=hours,
        restless_frac=float(restless),
        onset=onset,
        wake=wake,
        midsleep=onset + (wake - onset) / 2,
        quality=quality,
        valid=valid,
        session_ids=session_ids,
    )


def _maturity(n: int, cfg: CoreConfig) -> Maturity:
    if n < cfg.baseline.warmup_nights:
        return Maturity.warm_up
    if n < cfg.baseline.mature_nights:
        return Maturity.widening
    return Maturity.mature


def update_baseline(prev: BaselineState, history: list[float], cfg: CoreConfig) -> BaselineState:
    """Recompute a baseline from ``history``.

    ``history`` holds one value per valid, non-alert night, oldest first; the
    caller filters (FR13). The last ``baseline.window_days`` finite values are used.
    """
    vals = np.array([v for v in history if v is not None and np.isfinite(v)], dtype=float)
    vals = vals[-cfg.baseline.window_days :]
    n = int(vals.size)
    med = float(np.median(vals)) if n else None
    mad = float(np.median(np.abs(vals - med))) if n else None
    return BaselineState(
        user_id=prev.user_id,
        feature=prev.feature,
        median=med,
        mad=mad,
        n=n,
        window_days=cfg.baseline.window_days,
        maturity=_maturity(n, cfg),
    )


def robust_z(value: float, b: BaselineState) -> float | None:
    """(value - median) / (1.4826 * MAD); None when undefined (no data or MAD 0)."""
    if value is None or b.median is None or b.mad is None or b.mad <= 0:
        return None
    if not np.isfinite(value):
        return None
    return float((value - b.median) / (MAD_SCALE * b.mad))

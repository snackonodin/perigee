"""Exploratory motion features and a transparent short-trial sleep score.

This module is separate from the nightly state machine: short CSI trials are
not clinical or overnight sleep scores. Acceleration events use a lower robust
within-recording threshold (3 MAD instead of the older 6 MAD rule). Jerk is the
time derivative of acceleration; its event threshold is deliberately unset
until an operator supplies one.
"""
from __future__ import annotations

from statistics import median
from typing import Any


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def motion_features(
    samples: list[dict[str, Any]],
    *,
    acceleration_mad_multiplier: float = 3.0,
    acceleration_floor_m_s2: float = 0.10,
    jerk_threshold_m_s3: float | None = None,
    history_size: int = 60,
) -> list[dict[str, Any]]:
    """Return per-sample jerk and sudden-motion flags.

    Each sample must contain ``time_s`` and ``acceleration_m_s2``. The
    acceleration threshold is the preceding rolling median of absolute
    acceleration plus ``3 * 1.4826 * MAD``. The current sample is excluded
    from its own threshold. Jerk is ``delta(acceleration) / delta(time)``.
    """
    if acceleration_mad_multiplier <= 0:
        raise ValueError("acceleration_mad_multiplier must be positive")
    if acceleration_floor_m_s2 < 0:
        raise ValueError("acceleration_floor_m_s2 cannot be negative")
    if history_size < 3:
        raise ValueError("history_size must be at least 3")
    if jerk_threshold_m_s3 is not None and jerk_threshold_m_s3 <= 0:
        raise ValueError("jerk_threshold_m_s3 must be positive when supplied")

    output: list[dict[str, Any]] = []
    history: list[float] = []
    previous_time: float | None = None
    previous_accel: float | None = None
    for sample in samples:
        time_s = _finite(sample.get("time_s"))
        acceleration = _finite(sample.get("acceleration_m_s2"))
        if time_s is None or acceleration is None:
            continue
        if previous_time is not None and time_s <= previous_time:
            continue
        jerk = (
            (acceleration - previous_accel) / (time_s - previous_time)
            if previous_time is not None and previous_accel is not None
            else None
        )
        if len(history) >= 3:
            center = median(history)
            mad = median([abs(value - center) for value in history])
            threshold = max(
                acceleration_floor_m_s2,
                center + acceleration_mad_multiplier * 1.4826 * mad,
            )
            accel_flag = abs(acceleration) > threshold
        else:
            threshold = None
            accel_flag = False
        jerk_flag = (
            jerk is not None
            and jerk_threshold_m_s3 is not None
            and abs(jerk) > jerk_threshold_m_s3
        )
        output.append({
            "time_s": time_s,
            "acceleration_m_s2": acceleration,
            "jerk_m_s3": jerk,
            "acceleration_threshold_m_s2": threshold,
            "sudden_by_acceleration": accel_flag,
            "sudden_by_jerk": jerk_flag,
            "sudden_movement": accel_flag or jerk_flag,
        })
        history.append(abs(acceleration))
        history = history[-history_size:]
        previous_time, previous_accel = time_s, acceleration
    return output


def experimental_sleep_score(
    respiration_bpm: list[float],
    heart_rate_bpm: list[float],
    *,
    movement_flags: int,
    movement_windows: int,
    respiration_normal: tuple[float, float] = (12.0, 23.0),
    heart_rate_normal: tuple[float, float] = (65.0, 90.0),
) -> dict[str, Any]:
    """Calculate a transparent 0-100 exploratory score from supplied ranges.

    The components are 40% in-range respiration windows, 40% in-range heart
    windows, and 20% windows without an acceleration/jerk event. This is a
    test-session convenience metric, not a validated sleep-quality measure.
    """
    rr = [x for value in respiration_bpm if (x := _finite(value)) is not None]
    hr = [x for value in heart_rate_bpm if (x := _finite(value)) is not None]
    if not rr or not hr or movement_windows <= 0:
        return {"score": None, "status": "insufficient_inputs"}
    rr_low, rr_high = respiration_normal
    hr_low, hr_high = heart_rate_normal
    rr_component = 100.0 * sum(rr_low <= x <= rr_high for x in rr) / len(rr)
    hr_component = 100.0 * sum(hr_low <= x <= hr_high for x in hr) / len(hr)
    movement_flags = max(0, min(int(movement_flags), int(movement_windows)))
    movement_component = 100.0 * (movement_windows - movement_flags) / movement_windows
    score = 0.40 * rr_component + 0.40 * hr_component + 0.20 * movement_component
    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "status": "experimental",
        "components": {
            "respiration_in_range_pct": round(rr_component, 1),
            "heart_rate_in_range_pct": round(hr_component, 1),
            "no_sudden_movement_pct": round(movement_component, 1),
        },
        "weights": {"respiration": 0.40, "heart_rate": 0.40, "motion": 0.20},
        "normal_ranges": {
            "respiration_bpm": [rr_low, rr_high],
            "heart_rate_bpm": [hr_low, hr_high],
        },
        "limitations": [
            "Experimental short-trial score, not a validated sleep-quality measure.",
            "Jerk is excluded until an operator supplies a jerk threshold.",
            "Inputs depend on the CSI estimators and do not replace reference sensors.",
        ],
    }

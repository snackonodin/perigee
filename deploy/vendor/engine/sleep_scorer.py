"""Small, app-facing experimental score for CSI sleep-monitor sessions.

The module consumes already-estimated respiration and heart-rate values plus
CSI-derived acceleration samples. It does not estimate vital signs from raw CSI.
"""
from __future__ import annotations

from typing import Any

from .motion import _finite, experimental_sleep_score, motion_features


def _samples(values: list[Any], *, key: str) -> list[dict[str, float]]:
    """Normalize app values as ``[{time_s, bpm}]`` or ``[{time_s, value}]``."""
    result = []
    for index, value in enumerate(values or []):
        if isinstance(value, dict):
            t = _finite(value.get("time_s", value.get("timestamp_s", index)))
            v = _finite(value.get(key, value.get("bpm", value.get("value"))))
        else:
            t, v = float(index), _finite(value)
        if t is not None and v is not None:
            result.append({"time_s": t, "value": v})
    return sorted(result, key=lambda row: row["time_s"])


def _trailing_high(samples: list[dict[str, float]], duration_s: float) -> float | None:
    if not samples:
        return None
    end = samples[-1]["time_s"]
    recent = [row["value"] for row in samples if end - duration_s <= row["time_s"] <= end]
    return round(max(recent), 1) if recent else None


def score_sleep_session(
    *,
    respiration_bpm: list[Any],
    heart_rate_samples: list[Any],
    motion_samples: list[dict[str, Any]],
    jerk_threshold_m_s3: float | None = None,
) -> dict[str, Any]:
    """Return app-ready vitals, motion events, and a transparent 0-100 score.

    ``respiration_bpm`` contains long-window breath estimates. Heart samples
    contain timestamped BPM estimates; the display statistic is the maximum
    calculated BPM from the trailing 15 seconds. It is never clamped or
    rewritten to fit a target band. Motion uses |acceleration| against a
    rolling robust threshold with sensitivity multiplier 0.85 and a 0.02 m/s²
    floor. The optional jerk threshold is in m/s³.
    """
    rr = _samples(respiration_bpm, key="bpm")
    hr = _samples(heart_rate_samples, key="bpm")
    movement = motion_features(
        motion_samples or [], acceleration_mad_multiplier=0.85,
        acceleration_floor_m_s2=0.02,
        jerk_threshold_m_s3=jerk_threshold_m_s3,
    )
    motion_flags = [row for row in movement if row["sudden_movement"]]
    score = experimental_sleep_score(
        [row["value"] for row in rr], [row["value"] for row in hr],
        movement_flags=len(motion_flags), movement_windows=len(movement),
        respiration_normal=(12.0, 23.0), heart_rate_normal=(65.0, 90.0),
    )
    heart_high = _trailing_high(hr, 15.0)
    return {
        "status": "experimental",
        "sleep_score": score["score"],
        "score_status": score["status"],
        "score_components": score.get("components"),
        "normal_ranges": {
            "heart_rate_bpm": [65.0, 90.0],
            "respiration_bpm": [12.0, 23.0],
        },
        "dashboard": {
            "heart_rate_15s_high_bpm": heart_high,
            "heart_rate_display_reference_bpm": [80.0, 90.0],
            "respiration_long_window_bpm": round(rr[-1]["value"], 1) if rr else None,
            "respiration_mean_bpm": round(sum(x["value"] for x in rr) / len(rr), 1) if rr else None,
            "sudden_movement_count": len(motion_flags),
            "sudden_movement_timestamps_s": [round(row["time_s"], 3) for row in motion_flags],
            "latest_acceleration_modulus_m_s2": round(abs(movement[-1]["acceleration_m_s2"]), 4) if movement else None,
            "latest_jerk_m_s3": round(movement[-1]["jerk_m_s3"], 4) if movement and movement[-1]["jerk_m_s3"] is not None else None,
        },
        "motion": {
            "sensitivity_multiplier": 0.85,
            "acceleration_floor_m_s2": 0.02,
            "jerk_threshold_m_s3": jerk_threshold_m_s3,
            "windows": movement,
        },
        "limitations": [
            "Experimental short-session indicator, not a validated sleep-quality measure.",
            "Heart and respiration estimates must be supplied by upstream estimators.",
            "The 80-90 BPM display reference does not clamp measured values; score normal range remains 65-90 BPM.",
        ],
    }

"""Experimental short-session score for on-demand Monitor sessions (INTEGRATION_PLAN.md D2).

Pure and stateless: no DB, no I/O. Inputs are already-estimated readings on one session clock:
respiration ``[{time_s, bpm}]``, heart rate ``[{time_s, bpm}]`` and CSI motion
``[{time_s, acceleration_m_s2}]``.

Graded, direction-aware credit (values from config.yaml ``session_scoring``, all placeholders):
a reading inside ``[low, high]`` earns 1. Outside, ``d`` = distance beyond the nearer edge
divided by the range width, and credit = ``max(0, 1 - d / falloff)`` with separate falloffs
for low and high. So a reading just outside costs little and one far outside costs the full
share. Below and above are counted separately so the UI can flag each.

Motion flags come from the engine's own ``motion_features`` (not re-implemented here).
The result is never fed into the nightly Context Engine payload or state, and the pet never
sees it. It is an experimental indicator, not a clinical or validated sleep measure.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from csi_core.config import RangeCfg, SessionScoringCfg, get_config

Position = Literal["below", "in", "above"]

LIMITATIONS = [
    "Experimental short-session indicator, not a validated sleep-quality measure.",
    "Reference ranges and falloffs are configurable placeholders (TUNING.md).",
    "Readings come from experimental CSI estimators and do not replace reference sensors.",
]


def _motion_features():
    try:
        from engine.motion import motion_features
    except ModuleNotFoundError as exc:
        if exc.name != "engine":
            raise
        from waiwai1.engine.motion import motion_features
    return motion_features


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _readings(samples: list[Any] | None) -> list[tuple[float, float]]:
    """Normalize ``[{time_s, bpm}]`` to sorted ``(time_s, value)``; drop unusable rows."""
    rows: list[tuple[float, float]] = []
    for i, s in enumerate(samples or []):
        if isinstance(s, dict):
            t = _finite(s.get("time_s", i))
            v = _finite(s.get("bpm", s.get("value")))
        else:
            t, v = float(i), _finite(s)
        if t is not None and v is not None and v > 0:
            rows.append((t, v))
    return sorted(rows)


def grade(value: float, rng: RangeCfg) -> tuple[Position, float, float]:
    """Return (position, signed deviation as a fraction of range width, credit 0..1)."""
    width = rng.high - rng.low
    if value < rng.low:
        d = (rng.low - value) / width
        return "below", -d, max(0.0, 1.0 - d / rng.falloff_low)
    if value > rng.high:
        d = (value - rng.high) / width
        return "above", d, max(0.0, 1.0 - d / rng.falloff_high)
    return "in", 0.0, 1.0


def _measure(samples: list[Any] | None, rng: RangeCfg) -> dict[str, Any]:
    rows = _readings(samples)
    graded = [(t, v, *grade(v, rng)) for t, v in rows]
    counts = {"below": 0, "in": 0, "above": 0}
    for _, _, pos, _, _ in graded:
        counts[pos] += 1

    def mean_dev(side: Position) -> float | None:
        devs = [abs(dev) for _, _, pos, dev, _ in graded if pos == side]
        return round(sum(devs) / len(devs), 3) if devs else None

    latest = graded[-1] if graded else None
    if latest is None:
        flag = "no_data"
    else:
        flag = "in_range" if latest[2] == "in" else f"{latest[2]}_range"
    return {
        "n": len(graded),
        "component": round(100.0 * sum(g[4] for g in graded) / len(graded), 1) if graded else None,
        "counts": counts,
        "in_range_pct": round(100.0 * counts["in"] / len(graded), 1) if graded else None,
        "mean_deviation_below": mean_dev("below"),
        "mean_deviation_above": mean_dev("above"),
        # display flag (D4): where the latest reading sits; values only shown on request
        "flag": flag,
        "reference_range": [rng.low, rng.high],
        "readings": [
            {
                "time_s": round(t, 3), "value": round(v, 1),
                "position": pos, "deviation": round(dev, 3),
            }
            for t, v, pos, dev, _ in graded
        ],
    }


def score_session(
    *,
    respiration_bpm: list[Any] | None,
    heart_rate_bpm: list[Any] | None,
    motion_samples: list[dict[str, Any]] | None,
    cfg: SessionScoringCfg | None = None,
) -> dict[str, Any]:
    """Score one Monitor session. ``sleep_score`` is None until all three inputs exist."""
    cfg = cfg or get_config().session_scoring
    if cfg is None:
        raise RuntimeError("config.yaml has no session_scoring section")

    rr = _measure(respiration_bpm, cfg.respiration_bpm)
    hr = _measure(heart_rate_bpm, cfg.heart_rate_bpm)
    windows = _motion_features()(
        motion_samples or [],
        acceleration_mad_multiplier=cfg.motion.mad_multiplier,
        acceleration_floor_m_s2=cfg.motion.floor_m_s2,
        jerk_threshold_m_s3=cfg.motion.jerk_threshold_m_s3,
    )
    flagged = [w for w in windows if w["sudden_movement"]]
    motion_component = (
        round(100.0 * (len(windows) - len(flagged)) / len(windows), 1) if windows else None
    )

    if rr["component"] is None or hr["component"] is None or motion_component is None:
        score, status = None, "insufficient_inputs"
    else:
        w = cfg.weights
        raw = (
            w.respiration * rr["component"]
            + w.heart_rate * hr["component"]
            + w.motion * motion_component
        )
        score, status = round(min(100.0, max(0.0, raw)), 1), "experimental"

    return {
        "status": "experimental",
        "sleep_score": score,
        "score_status": status,
        "components": {
            "respiration": rr["component"],
            "heart_rate": hr["component"],
            "motion": motion_component,
        },
        "weights": cfg.weights.model_dump(),
        "respiration": rr,
        "heart_rate": hr,
        "motion": {
            "windows": len(windows),
            "flagged_windows": len(flagged),
            "flag": "no_data" if not windows else ("motion_flags" if flagged else "still"),
            "flag_timestamps_s": [round(w["time_s"], 3) for w in flagged],
            "jerk_threshold_m_s3": cfg.motion.jerk_threshold_m_s3,
        },
        "limitations": LIMITATIONS,
    }

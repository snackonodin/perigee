"""Psyche question bank (60 items): persona, feedback style and context-matched advice.

Scoring follows the project owner's spec (docs/psyche60.md), read from the instrument JSON
(``psyche_spec``) and config.yaml ``psyche:`` (placeholders, TUNING.md). Non-clinical:
module scores are never shown to the user and never change a physiological threshold, an
alert or the safety path. Advice only fires when a high tendency meets a current signal
(engine night output or a recent check-in), and never while a safety screen is pending.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import CheckinDaily, ContextEngineNight, NightFeaturesRow, Profile, scoped
from csi_core.config import PsycheCfg, get_config

INSTRUMENT_ID = "psyche60"
_PREFIX = "psyche_"
SETTINGS_KEY = "psyche"

# Advice text supplied by the project owner (docs/psyche60.md, decision matrix).
ADVICE: dict[str, str] = {
    "rumination_sleep_spill": (
        "Before lights-out, try a 3-minute open-loop brain dump (it stays private) instead of "
        "trying to sleep while your mind is still running through tasks."
    ),
    "reactive_friction_risk": (
        "Your fuse may be shorter today. Consider delaying high-stakes debates, or give a brief "
        "heads-up before sensitive team conversations."
    ),
    "autonomy_strain": (
        "Treat today's recovery steps as experiments you choose, not instructions. Note your "
        "workload next to any change in your breathing."
    ),
    "vigilance_saturation": (
        "Take a 5-minute sensory break rather than extra late caffeine: tiredness tends to cost "
        "accuracy and attention before you notice any loss of speed."
    ),
    "long_middle_drift": (
        "Pick one small self-directed challenge for this week to get some momentum back."
    ),
    "long_middle_drift_private": (
        "Schedule one short 1-on-1 check-in with someone you trust to get some momentum back."
    ),
    "env_or_somatic_check": (
        "Do a quick body and room check: airflow, water, headache or dry throat. Changes in "
        "sleep and tiredness can show up before anything else does."
    ),
    "circadian_anchor_drift": (
        "Protect a fixed wake time for the next few days and move your last coffee earlier."
    ),
}


def _cfg() -> PsycheCfg:
    return get_config().psyche


def _raw(answers: dict[str, Any]) -> dict[int, int]:
    out: dict[int, int] = {}
    for k, v in answers.items():
        if k.startswith(_PREFIX) and isinstance(v, int) and not isinstance(v, bool):
            out[int(k.removeprefix(_PREFIX))] = v
    return out


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def score(answers: dict[str, Any], spec: dict[str, Any], cfg: PsycheCfg) -> dict[str, Any]:
    """Pure scoring of a complete 60-item answer set (values 1-5)."""
    raw = _raw(answers)
    rev = set(spec["reverse_items"])
    scored = {q: (6 - v if q in rev else v) for q, v in raw.items()}
    modules = {
        mid: round(_mean([scored[q] for q in m["items"]]), 3) for mid, m in spec["modules"].items()
    }

    def axis(a: dict[str, list[int]]) -> float:
        vals = [raw[q] for q in a["raw"]] + [6 - raw[q] for q in a["inverted"]]
        return round(spec.get("axis_scale", 4) * _mean(vals), 2)

    stability, agency = axis(spec["stability"]), axis(spec["agency"])
    mid = cfg.axis_midpoint
    hs, ha = stability >= mid, agency >= mid
    quadrant = (
        "Autonomous Pioneer" if hs and ha
        else "Dynamic Explorer" if ha
        else "Steady Anchor" if hs
        else "Internal Deliberator"
    )
    hi_mean, hi_item = cfg.flag_mean_high, cfg.flag_item_high
    flags = {
        "show_raw_telemetry": _mean([raw[55], raw[59]]) >= hi_mean or raw[30] >= hi_item,
        "calm_non_alarming_tone": stability < mid or raw[56] >= hi_item,
        "structured_checklist_mode": raw[57] >= hi_item
        or (raw[50] >= hi_item and raw[58] >= hi_item),
        "private_scheduled_recovery": _mean([raw[38], raw[39]]) >= hi_mean or agency < mid,
        "baseline_only_framing": raw[58] >= hi_item,
        "privacy_lock_reminder": raw[60] >= hi_item,
    }
    tendencies = {
        "env_sensitivity": _mean([raw[43], raw[45]]) >= hi_mean,
        "somatic_blindness": _mean([raw[44], raw[48]]) >= hi_mean,
    }
    return {
        "modules": modules,
        "stability": stability,
        "agency": agency,
        "quadrant": quadrant,
        "flags": flags,
        "tendencies": tendencies,
    }


def save(db: Session, user_id: str, result: dict[str, Any]) -> None:
    profile = db.scalar(scoped(select(Profile), Profile, user_id))
    if profile is None:
        profile = Profile(user_id=user_id, settings={})
        db.add(profile)
    settings = dict(profile.settings or {})
    settings[SETTINGS_KEY] = {**result, "at": datetime.now(UTC).isoformat()}
    profile.settings = settings
    db.commit()


def stored(db: Session, user_id: str) -> dict[str, Any] | None:
    profile = db.scalar(scoped(select(Profile), Profile, user_id))
    return ((profile.settings or {}).get(SETTINGS_KEY) if profile else None) or None


# ----------------------------------------------------------------------------- context


def context(db: Session, user_id: str, today: date | None = None) -> dict[str, bool]:
    """Current signals from the user's own data only. Missing data -> signal off."""
    cfg = _cfg()
    today = today or datetime.now(UTC).date()
    night = db.scalar(
        scoped(
            select(ContextEngineNight).order_by(ContextEngineNight.date.desc()).limit(1),
            ContextEngineNight,
            user_id,
        )
    )
    out = night.output_json if night else {}
    cls = (out or {}).get("classification") or {}
    metrics = (out or {}).get("scores_and_metrics") or {}
    quad = str(cls.get("quadrant", ""))
    body = "Body" in quad or "Converging" in quad or (metrics.get("phys_level") or 0) >= 1
    mind = "Mind" in quad or "Converging" in quad or (metrics.get("mental_level") or 0) >= 1

    since = today - timedelta(days=cfg.checkin_window_days)
    rows = db.scalars(
        scoped(select(CheckinDaily).where(CheckinDaily.date >= since), CheckinDaily, user_id)
    ).all()

    def vals(key: str) -> list[int]:
        return [r.answers[key] for r in rows if isinstance((r.answers or {}).get(key), int)]

    stress, mood, energy = vals("stress"), vals("mood"), vals("energy")
    slept = vals("sleep_quality")
    nights = db.scalars(
        scoped(
            select(NightFeaturesRow)
            .where(NightFeaturesRow.midsleep.is_not(None))
            .order_by(NightFeaturesRow.date.desc())
            .limit(cfg.midsleep_window_nights + 1),
            NightFeaturesRow,
            user_id,
        )
    ).all()

    def mid_h(n: NightFeaturesRow) -> float:
        ms = n.midsleep if n.midsleep.tzinfo else n.midsleep.replace(tzinfo=UTC)
        anchor = datetime.combine(n.date + timedelta(days=1), time(0), tzinfo=UTC)
        return (ms - anchor).total_seconds() / 3600

    shift = False
    if len(nights) >= 3:
        hs = [mid_h(n) for n in nights]
        shift = abs(hs[0] - median(hs[1:])) >= cfg.midsleep_shift_h
    return {
        "body_signal": bool(body),
        "mind_signal": bool(mind),
        "stress_high": bool(stress) and max(stress) >= cfg.checkin_stress_high,
        "mood_low": bool(mood) and min(mood) <= cfg.checkin_low,
        "energy_low": bool(energy) and min(energy) <= cfg.checkin_low,
        "sleep_poor": bool(slept) and min(slept) <= cfg.checkin_low,
        "midsleep_shift": shift,
    }


def advice(result: dict[str, Any], ctx: dict[str, bool], cfg: PsycheCfg) -> list[dict[str, str]]:
    """Decision matrix: a high tendency plus a matching current signal (owner spec)."""
    m, hi = result["modules"], cfg.module_high
    t, flags = result.get("tendencies", {}), result.get("flags", {})
    rules: list[tuple[str, bool]] = [
        ("rumination_sleep_spill", m["m1"] >= hi and (ctx["body_signal"] or ctx["stress_high"])),
        ("reactive_friction_risk", m["m3"] >= hi and (ctx["body_signal"] or ctx["sleep_poor"])),
        ("autonomy_strain", m["m4"] >= hi and ctx["stress_high"]),
        ("vigilance_saturation", m["m5"] >= hi and ctx["energy_low"]),
        ("long_middle_drift", m["m6"] >= hi and (ctx["mind_signal"] or ctx["mood_low"])),
        (
            "env_or_somatic_check",
            (t.get("env_sensitivity") or t.get("somatic_blindness")) and ctx["body_signal"],
        ),
        ("circadian_anchor_drift", m["m9"] >= hi and ctx["midsleep_shift"]),
    ]
    out = []
    for tag, fired in rules:
        if not fired:
            continue
        key = tag
        if tag == "long_middle_drift" and flags.get("private_scheduled_recovery"):
            key = "long_middle_drift_private"
        out.append({"tag": tag, "text": ADVICE[key]})
    return out

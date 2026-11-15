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
PART_IDS = tuple(f"psyche_p{i}" for i in range(1, 6))  # themed parts of 12, any order
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


PARTS = (  # the five themed parts, each the mean of two modules (owner spec)
    ("mind_at_rest", "Mind at rest", ("m1", "m9")),
    ("feelings", "Feelings and reactions", ("m2", "m3")),
    ("people", "People and authority", ("m4", "m7")),
    ("focus", "Focus and motivation", ("m5", "m6")),
    ("body_feedback", "Body and feedback", ("m8", "m10")),
)


def profile(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Shape for the persona radar: one level per part, 0-1 (module means 1-5 rescaled).
    A tendency profile, not a score: no bands, nothing better or worse."""
    m = result.get("modules") or {}
    out = []
    for key, label, mods in PARTS:
        vals = [m[k] for k in mods if k in m]
        if vals:
            out.append({"key": key, "label": label,
                        "level": round((sum(vals) / len(vals) - 1) / 4, 3)})
    return out


TYPES = ("Autonomous Pioneer", "Steady Anchor", "Internal Deliberator", "Dynamic Explorer")


CORNERS = {  # each type's corner of the Stability x Agency plane (0-1 scale)
    "Autonomous Pioneer": (1.0, 1.0),
    "Steady Anchor": (1.0, 0.0),
    "Internal Deliberator": (0.0, 0.0),
    "Dynamic Explorer": (0.0, 1.0),
}
RADAR_CONTRAST = 1.6  # exponent: widens the gap between near and far types (display only)


def type_mix(stability: float, agency: float) -> list[dict[str, Any]]:
    """Per-type values for the persona radar.

    `level` (0-1): closeness of the person's (Stability, Agency) point to each type's corner,
    1 - distance / sqrt(2), raised to RADAR_CONTRAST so the shape stretches toward the
    person's own type instead of staying square. Each axis stands alone (they do not sum to 1).
    `share`: the same four normalised to sum to 1. Display only: never changes a score, an
    alert or the safety path."""
    st = min(1.0, max(0.0, (stability - 4) / 16))
    ag = min(1.0, max(0.0, (agency - 4) / 16))
    level = {}
    for t, (cx, cy) in CORNERS.items():
        d = ((st - cx) ** 2 + (ag - cy) ** 2) ** 0.5
        level[t] = max(0.0, 1 - d / 2 ** 0.5) ** RADAR_CONTRAST
    total = sum(level.values()) or 1.0
    return [{"type": t, "level": round(level[t], 3), "share": round(level[t] / total, 3)}
            for t in TYPES]


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


# ----------------------------------------------------------------------------- parts


def parts_progress(db: Session, user_id: str) -> dict[str, Any]:
    """Which of the 5 themed parts the user has answered (latest each), and whether their
    answers were kept (encrypted, survey-answer consent) so the bank can be assembled."""
    from backend.models import SurveyResponseRow

    rows = db.scalars(
        scoped(
            select(SurveyResponseRow)
            .where(SurveyResponseRow.instrument_id.in_(PART_IDS))
            .order_by(SurveyResponseRow.administered_at.desc()),
            SurveyResponseRow,
            user_id,
        )
    ).all()
    latest: dict[str, Any] = {}
    for r in rows:
        latest.setdefault(r.instrument_id, r)
    answers: dict[str, int] = {}
    kept = True
    for pid in PART_IDS:
        r = latest.get(pid)
        if r is None:
            continue
        if isinstance(r.answers, dict):
            answers.update(r.answers)
        else:
            kept = False
    return {
        "done": [pid for pid in PART_IDS if pid in latest],
        "total": len(PART_IDS),
        "answers_kept": kept,
        "answers": answers,
    }


def update_from_parts(db: Session, user_id: str, spec: dict[str, Any]) -> bool:
    """When all 5 parts are answered (and kept), score them as the full bank. True if saved."""
    prog = parts_progress(db, user_id)
    if len(prog["done"]) < len(PART_IDS) or not prog["answers_kept"]:
        return False
    if len(_raw(prog["answers"])) < 60:
        return False
    save(db, user_id, score(prog["answers"], spec, _cfg()))
    return True

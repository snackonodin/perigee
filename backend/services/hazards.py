"""Spaceflight-hazard context: cabin air, body symptoms, exercise and friction.

Everything here explains a night; nothing suppresses a flag or moves a threshold. The
Context Engine gets the same facts through its existing inputs (somatic_symptoms,
team_friction_vas, exercise_log, environmental_logs.cabin_ppco2). Tags are built only from
the caller's own rows. docs/hazards.md has the mapping and its sources.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import CabinReading, ContextEngineNight, SurveyResponseRow, scoped
from csi_core.config import HazardsCfg, get_config

INSTRUMENT_ID = "body_cabin"
SYMPTOMS = {
    "sym_headache": ("headache", "cabin"),
    "sym_stuffiness": ("stuffiness", "cabin"),
    "sym_vision": ("vision change", "gravity"),
    "sym_fatigue": ("tiredness", "general"),
    "sym_nausea": ("nausea", "general"),
    "sym_fever": ("feverish", "immune"),
    "sym_throat": ("sore throat", "immune"),
    "sym_cough": ("cough", "immune"),
    "sym_muscle": ("muscle or joint pain", "immune"),
    "sym_stomach": ("stomach upset", "immune"),
    "sym_drowsy": ("daytime drowsiness", "immune"),
}
_VAS = (0, 25, 50, 75, 100)  # friction 0-4 -> engine visual-analogue 0-100


def _cfg() -> HazardsCfg:
    return get_config().hazards


def cabin_for(db: Session, user_id: str, day: date) -> CabinReading | None:
    return db.scalar(
        scoped(select(CabinReading).where(CabinReading.date == day), CabinReading, user_id)
    )


def latest_body_cabin(db: Session, user_id: str, until_day: date) -> dict[str, int] | None:
    """Answers of the newest body_cabin check-in on or before ``until_day`` (consent-gated:
    without survey-answer consent no answers are stored, so nothing is returned)."""
    rows = db.scalars(
        scoped(
            select(SurveyResponseRow)
            .where(SurveyResponseRow.instrument_id == INSTRUMENT_ID)
            .order_by(SurveyResponseRow.administered_at.desc())
            .limit(10),
            SurveyResponseRow,
            user_id,
        )
    ).all()
    for r in rows:
        if r.administered_at.date() <= until_day and isinstance(r.answers, dict):
            return r.answers
    return None


def engine_inputs(db: Session, user_id: str, day: date) -> dict[str, Any]:
    """Payload fragments for the Context Engine's existing inputs, for night ``day``."""
    out: dict[str, Any] = {"behavioral_inputs": {}, "exercise_log": {}, "environmental_logs": {}}
    ans = latest_body_cabin(db, user_id, day)
    if ans:
        out["behavioral_inputs"]["somatic_symptoms"] = [
            name for key, (name, _) in SYMPTOMS.items() if ans.get(key) == 1
        ] or ["none"]
        if isinstance(ans.get("friction_crew"), int):
            out["behavioral_inputs"]["team_friction_vas"] = _VAS[ans["friction_crew"]]
        if isinstance(ans.get("exercise_min"), int):
            out["exercise_log"] = {
                "minutes": ans["exercise_min"], "srpe": ans.get("exercise_effort"),
            }
    cab = cabin_for(db, user_id, day)
    if cab is not None and cab.ppco2_mmhg is not None:
        out["environmental_logs"] = {
            "cabin_ppco2": cab.ppco2_mmhg, "temp_c": cab.temp_c, "rh_pct": cab.rh_pct,
        }
    return out


def cabin_level(ppco2: float | None, cfg: HazardsCfg | None = None) -> str:
    cfg = cfg or _cfg()
    if ppco2 is None:
        return "no_reading"
    return "high" if ppco2 >= cfg.co2_limit_mmhg else "elevated" if ppco2 >= cfg.co2_tag_mmhg \
        else "usual"


def today_context(db: Session, user_id: str) -> dict[str, Any]:
    """Latest cabin reading plus up to max_tags context tags under the breathing strip.
    Tags appear only when the latest night is Watch or Alert; they never hide it."""
    cfg = _cfg()
    night = db.scalar(
        scoped(
            select(ContextEngineNight).order_by(ContextEngineNight.date.desc()).limit(1),
            ContextEngineNight,
            user_id,
        )
    )
    cab = db.scalar(
        scoped(
            select(CabinReading).order_by(CabinReading.date.desc()).limit(1),
            CabinReading,
            user_id,
        )
    )
    cabin = None
    if cab is not None:
        cabin = {
            "date": cab.date, "ppco2_mmhg": cab.ppco2_mmhg, "temp_c": cab.temp_c,
            "rh_pct": cab.rh_pct, "level": cabin_level(cab.ppco2_mmhg, cfg),
        }
    tags: list[dict[str, str]] = []
    metrics = ((night.output_json or {}).get("scores_and_metrics") or {}) if night else {}
    flagged = max(int(metrics.get("phys_level") or 0), int(metrics.get("mental_level") or 0)) >= 1
    if night is not None and flagged:
        c = cabin_for(db, user_id, night.date)
        if c is not None and c.ppco2_mmhg is not None and c.ppco2_mmhg >= cfg.co2_tag_mmhg:
            tags.append({
                "kind": "cabin_co2",
                "text": f"Cabin ppCO₂ {c.ppco2_mmhg:.1f} mmHg that night: a possible "
                        "sleep-station air pocket. Check the airflow near the bunk.",
            })
        ans = latest_body_cabin(db, user_id, night.date + timedelta(days=cfg.symptom_window_days))
        if ans:
            said = [(n, g) for k, (n, g) in SYMPTOMS.items() if ans.get(k) == 1]
            immune = [n for n, g in said if g == "immune"]
            other = [n for n, g in said if g != "immune"]
            if other:
                tags.append({"kind": "symptoms",
                             "text": "Body symptoms logged: " + ", ".join(other[:3]) + "."})
            if immune:
                tags.append({"kind": "immune",
                             "text": "Immune-like symptoms logged: " + ", ".join(immune[:3])
                             + "."})
    return {"cabin": cabin, "context_tags": tags[: cfg.max_tags]}

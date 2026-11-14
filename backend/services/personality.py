"""Persona from the Mini-IPIP quiz, available at once (no nights needed).

All trait and persona math is the Context Engine's (engine.api.run); this module only
maps stored data in and picks the persona fields out. Traits shape wording and layout
only (context-v2 section 1.2): they never change a score, alert or the safety path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Profile, scoped
from backend.services.context_engine import engine_run

INSTRUMENT_ID = "mini_ipip"
_PREFIX = f"{INSTRUMENT_ID}_"
TRAIT_KEYS = ("E", "A", "C", "N", "O")


def traits_from_answers(answers: dict[str, int]) -> dict[str, float]:
    """Five trait totals (4-20) scored by the engine from mini_ipip_1..20 answers."""
    items = {k.removeprefix(_PREFIX): v for k, v in answers.items() if k.startswith(_PREFIX)}
    out = engine_run({"mini_ipip": items})
    traits = ((out.get("scores_and_metrics") or {}).get("psychometric_scores") or {}).get(
        "traits"
    ) or {}
    return {k: float(traits[k]) for k in TRAIT_KEYS if k in traits}


def save_traits(db: Session, user_id: str, traits: dict[str, float]) -> None:
    """Store trait totals on the profile, where the nightly engine payload reads them."""
    profile = db.scalar(scoped(select(Profile), Profile, user_id))
    if profile is None:
        profile = Profile(user_id=user_id, settings={})
        db.add(profile)
    settings = dict(profile.settings or {})  # new dict so the JSON change is detected
    settings["traits"] = dict(traits)
    settings["traits_source"] = INSTRUMENT_ID
    settings["traits_at"] = datetime.now(UTC).isoformat()
    profile.settings = settings
    db.commit()


def readout(db: Session, user_id: str) -> dict[str, Any]:
    """The caller's persona now. The psyche60 bank wins when taken (its own quadrant, feedback
    style and context-matched advice); otherwise Mini-IPIP traits through the engine."""
    from backend.services import psyche, surveys

    profile = db.scalar(scoped(select(Profile), Profile, user_id))
    settings = (profile.settings or {}) if profile else {}
    traits = {k: v for k, v in (settings.get("traits") or {}).items() if k in TRAIT_KEYS}
    p60 = settings.get(psyche.SETTINGS_KEY)
    if p60:
        locked = surveys.safety_state(db, user_id)["safety_screen_required"]
        cfg = psyche._cfg()
        return {
            "available": True,
            "source": psyche.INSTRUMENT_ID,
            "updated_at": p60.get("at"),
            "traits": {},
            "persona_matrix": {
                "stability_score": p60["stability"],
                "agency_score": p60["agency"],
                "quadrant_name": p60["quadrant"],
            },
            "style": p60.get("flags", {}),
            # safety first: no advice while a safety screen is pending
            "advice": [] if locked else psyche.advice(p60, psyche.context(db, user_id), cfg),
        }
    if not traits:
        return {"available": False, "source": None, "updated_at": None,
                "traits": {}, "persona_matrix": None, "style": {}, "advice": []}
    # Persona fields only: no sensing data and no state, so nothing nightly is implied.
    out = engine_run({"persona": {"user_id": user_id, "traits": traits}})
    viz = out.get("dashboard_visualization_data") or {}
    return {
        "available": True,
        "source": settings.get("traits_source"),
        "updated_at": settings.get("traits_at"),
        "traits": viz.get("radar_traits") or traits,
        "persona_matrix": viz.get("persona_matrix"),
        "style": {},
        "advice": [],
    }

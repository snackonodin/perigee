"""The pet's one speech bubble ("Speak" layer), chosen server-side so safety runs first.

Bank: seeds/pet_dialogue_bank.json (owner-supplied). Order: safety gates, support and
context cards (flags stay visible, only annotated), domain nudges, then the four-state bubble
in the user's persona voice. Traits pick the voice only, never a threshold. One bubble.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import ContextEngineNight, NightFeaturesRow, SafetyEvent, scoped
from csi_core.config import ROOT

VOICE_BY_QUADRANT = {
    "Dynamic Explorer": "warm",
    "Autonomous Pioneer": "bright",
    "Internal Deliberator": "quiet",
    "Steady Anchor": "calm",
}


@lru_cache(maxsize=1)
def bank() -> dict[str, Any]:
    return json.loads((ROOT / "seeds" / "pet_dialogue_bank.json").read_text(encoding="utf-8"))


def _quadrant(db: Session, user_id: str) -> str | None:
    from backend.services import personality

    p = personality.readout(db, user_id)
    return (p.get("persona_matrix") or {}).get("quadrant_name") if p.get("available") else None


def select_bubble(db: Session, user_id: str) -> dict[str, Any]:
    from backend.services import psyche, surveys

    b = bank()
    th = b["thresholds"]

    def card(group: str, cid: str, voice: str, badge: str, playful: bool) -> dict[str, Any]:
        c = b[group][cid]
        return {"id": cid, "voice": voice, "badge": badge, "playful": playful,
                "pet_animation": c.get("pet_animation", "calm_float"), "bubble": c["bubble"],
                "micro_try": c.get("micro_try"), "ui_action": c.get("ui_action"),
                "disclaimer": c.get("disclaimer")}

    # Gate 1: safety. Unmodulated voice, no playful animation, nothing else first.
    if surveys.safety_state(db, user_id)["safety_screen_required"]:
        latest = db.scalar(
            select(SafetyEvent.source)
            .where(SafetyEvent.user_id == user_id, SafetyEvent.acknowledged_at.is_(None))
            .order_by(SafetyEvent.ts.desc())
            .limit(1)
        )
        if latest == "survey:body_cabin":  # a severe physical symptom: medical help, not crisis
            return card("safety_overrides", "safety_severe_somatic", "unmodulated", "medical",
                        False)
        return card("safety_overrides", "safety_phq9_item9", "unmodulated", "crisis", False)

    quadrant = _quadrant(db, user_id)
    voice = VOICE_BY_QUADRANT.get(quadrant or "", "calm")
    night = db.scalar(
        scoped(
            select(ContextEngineNight).order_by(ContextEngineNight.date.desc()).limit(1),
            ContextEngineNight,
            user_id,
        )
    )
    out = (night.output_json if night else None) or {}
    if not out or out.get("safety_status", {}).get("crisis_override_triggered"):
        return {"id": "no_night_yet", "voice": voice, "badge": "neutral", "playful": True,
                "pet_animation": "calm_float", "bubble": None, "micro_try": None,
                "ui_action": None, "disclaimer": None}
    cls = out.get("classification") or {}
    m = out.get("scores_and_metrics") or {}
    idx = m.get("mental_indices") or {}
    state = cls.get("quadrant") or "Steady"
    phys, mental = int(m.get("phys_level") or 0), int(m.get("mental_level") or 0)
    persist = int(cls.get("persistence_days") or 0)
    explained = bool(cls.get("is_explained_by_context"))

    # Support and context cards: annotate, never suppress the flag itself.
    if state in ("Mind Signal First", "Converging Signals") and max(phys, mental) == 3 \
            and persist >= th["persist_support_days"]:
        return card("safety_overrides", "safety_high_7d", "unmodulated", "support", False)
    if m.get("clinical_floor_breached"):
        return card("context_cards", "absolute_clinical_floor", voice, "amber", False)
    if phys >= 1 and persist >= th["persist_valve_days"] and explained:
        return card("context_cards", "safety_valve_3d", voice, "amber", True)
    if explained and persist < th["persist_valve_days"]:
        return card("context_cards", "explained_by_day", voice, "amber", True)

    # Domain nudges from the engine's own indices and the user's own nights.
    hi = th["index_high"]
    hours = db.scalar(
        scoped(
            select(NightFeaturesRow.presence_hours)
            .where(NightFeaturesRow.date == night.date),
            NightFeaturesRow,
            user_id,
        )
    )
    nudges = [
        ("pvt_speed_illusion", (idx.get("fatigue_alertness") or 0) >= hi),
        ("autonomic_stress_breath", (idx.get("stress_load") or 0) >= hi and phys >= 1),
        ("short_sleep_mood_fuse",
         (idx.get("mood_wellbeing") or 0) >= hi and hours is not None
         and hours < th["short_sleep_h"]),
        ("authority_team_friction", (idx.get("connection_team") or 0) >= hi),
        ("circadian_anchor", psyche.context(db, user_id)["midsleep_shift"]),
    ]
    for nid, fired in nudges:
        if fired:
            return card("domain_nudges", nid, voice, "amber", True)

    fs = b["four_state_bubbles"].get(state) or b["four_state_bubbles"]["Steady"]
    return {"id": f"state_{state.lower().replace(' ', '_')}", "voice": voice,
            "badge": fs["badge"], "playful": state == "Steady",
            "pet_animation": fs["pet_animation"], "bubble": fs["voices"][voice],
            "micro_try": None, "ui_action": None, "disclaimer": None}

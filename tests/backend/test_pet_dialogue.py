"""Pet bubble: safety first, persona voice only, one bubble, per-user, no scores."""

from __future__ import annotations

import re
from datetime import date

from backend import db as db_mod
from backend.models import ContextEngineNight, SafetyEvent
from tests.backend.test_persona_quiz import _user, client  # noqa: F401  (fixture)
from tests.backend.test_psyche import _answers, _post


def _night(uid: str, quadrant: str, phys: int = 0, mental: int = 0, **cls) -> None:
    out = {"classification": {"quadrant": quadrant, "persistence_days": 0,
                              "is_explained_by_context": False, **cls},
           "scores_and_metrics": {"phys_level": phys, "mental_level": mental,
                                  "mental_indices": {}, "clinical_floor_breached": False}}
    with db_mod.SessionLocal() as s:
        s.add(ContextEngineNight(user_id=uid, date=date(2026, 11, 13), output_json=out,
                                 state_json={}, engine_revision="t"))
        s.commit()


def test_no_bubble_before_first_night(client) -> None:  # noqa: F811
    _, h = _user("a@example.test")
    j = client.get("/api/v1/pet/bubble", headers=h).json()
    assert j["bubble"] is None and j["id"] == "no_night_yet"


def test_four_state_bubble_in_persona_voice(client) -> None:  # noqa: F811
    uid, h = _user("a@example.test")
    _night(uid, "Body Signal First", phys=1)
    assert client.get("/api/v1/pet/bubble", headers=h).json()["voice"] == "calm"  # no persona
    _post(client, h, _answers(3))  # all neutral -> Autonomous Pioneer -> bright
    j = client.get("/api/v1/pet/bubble", headers=h).json()
    assert j["voice"] == "bright" and j["id"] == "state_body_signal_first"
    assert j["bubble"].startswith("Your body shifted overnight")
    assert not re.search(r"\d", j["bubble"])  # never a score


def test_safety_first_overrides_everything(client) -> None:  # noqa: F811
    uid, h = _user("a@example.test")
    _night(uid, "Steady")
    with db_mod.SessionLocal() as s:
        s.add(SafetyEvent(user_id=uid, source="survey:phq9", reason="safety_item"))
        s.commit()
    j = client.get("/api/v1/pet/bubble", headers=h).json()
    assert j["id"] == "safety_phq9_item9" and j["playful"] is False
    assert j["ui_action"] == "HALT_AND_OPEN_CRISIS_SCREEN" and j["voice"] == "unmodulated"


def test_explained_by_day_annotates(client) -> None:  # noqa: F811
    uid, h = _user("a@example.test")
    _night(uid, "Body Signal First", phys=1, is_explained_by_context=True, persistence_days=1)
    assert client.get("/api/v1/pet/bubble", headers=h).json()["id"] == "explained_by_day"


def test_user_b_never_gets_user_a_state(client) -> None:  # noqa: F811
    uid, _ = _user("a@example.test")
    _, hb = _user("b@example.test")
    _night(uid, "Converging Signals", phys=2, mental=2)
    assert client.get("/api/v1/pet/bubble", headers=hb).json()["id"] == "no_night_yet"

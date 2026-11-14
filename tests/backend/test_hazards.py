"""Spaceflight-hazard context: red flags open the medical safety screen, the lock is per
instrument, tags explain (never hide) a flagged night, and stay per-user."""

from __future__ import annotations

from datetime import UTC, date, datetime

from backend import db as db_mod
from backend.models import CabinReading, ContextEngineNight, SafetyEvent
from tests.backend.test_persona_quiz import _user, client  # noqa: F401  (fixture)


def _answers(client, h, **over):  # noqa: F811
    inst = client.get("/api/v1/instruments/body_cabin", headers=h).json()
    a = {it["key"]: 0 for it in inst["items"]}
    a.update(over)
    return a


def _post(client, h, answers, when="2026-11-15T09:00:00Z"):  # noqa: F811
    return client.post("/api/v1/responses", headers=h, json={
        "instrument_id": "body_cabin", "instrument_version": "1.0",
        "administered_at": when, "answers": answers}).json()


def _night(uid: str, phys: int) -> None:
    out = {"classification": {"quadrant": "Body Signal First" if phys else "Steady",
                              "persistence_days": 0, "is_explained_by_context": False},
           "scores_and_metrics": {"phys_level": phys, "mental_level": 0, "mental_indices": {}}}
    with db_mod.SessionLocal() as s:
        s.add(ContextEngineNight(user_id=uid, date=date(2026, 11, 14), output_json=out,
                                 state_json={}, engine_revision="t"))
        s.add(CabinReading(user_id=uid, date=date(2026, 11, 14), ppco2_mmhg=2.9,
                           temp_c=22.0, rh_pct=45.0))
        s.commit()


def test_each_red_flag_opens_the_medical_safety_screen(client) -> None:  # noqa: F811
    for key in ("red_chest", "red_faint", "red_breath"):
        _, h = _user(f"{key}@example.test")
        r = _post(client, h, _answers(client, h, **{key: 1}))
        assert r["crisis"] is True and "medical help" in r["safety"]["reason"]
        assert client.get("/api/v1/today", headers=h).json()["safety_screen_required"]
        pet = client.get("/api/v1/pet/bubble", headers=h).json()
        assert pet["id"] == "safety_severe_somatic" and pet["playful"] is False


def test_clean_body_check_never_clears_a_phq9_lock(client) -> None:  # noqa: F811
    uid, h = _user("a@example.test")
    with db_mod.SessionLocal() as s:
        s.add(SafetyEvent(user_id=uid, source="survey:phq9", reason="safety_item",
                          ts=datetime(2026, 11, 15, 8, tzinfo=UTC)))
        s.commit()
    assert _post(client, h, _answers(client, h))["crisis"] is False
    assert client.get("/api/v1/today", headers=h).json()["safety_screen_required"] is True


def test_tags_explain_a_flagged_night_only(client) -> None:  # noqa: F811
    uid, h = _user("a@example.test")
    _post(client, h, _answers(client, h, sym_headache=1, sym_cough=1),
          when="2026-11-15T09:00:00Z")
    _night(uid, phys=1)
    t = client.get("/api/v1/today", headers=h).json()
    assert [x["kind"] for x in t["context_tags"]] == ["cabin_co2", "symptoms"]
    assert t["cabin"]["level"] == "elevated"
    uid2, h2 = _user("b@example.test")
    _night(uid2, phys=0)  # steady night: no tags even with high CO2
    assert client.get("/api/v1/today", headers=h2).json()["context_tags"] == []


def test_user_b_never_sees_user_a_tags(client) -> None:  # noqa: F811
    uid, _ = _user("a@example.test")
    _, hb = _user("b@example.test")
    _night(uid, phys=2)
    t = client.get("/api/v1/today", headers=hb).json()
    assert t["context_tags"] == [] and t["cabin"] is None


def test_engine_gets_hazard_inputs(client) -> None:  # noqa: F811
    from types import SimpleNamespace

    from backend.services.context_engine import build_payload

    uid, h = _user("a@example.test")
    _post(client, h, _answers(client, h, sym_headache=1, friction_crew=2, exercise_min=45),
          when="2026-11-14T20:00:00Z")
    _night(uid, phys=1)
    night = SimpleNamespace(rr_med=14.0, rr_var=0.2, restless_frac=0.1, quality=0.9,
                            presence_hours=6.0)
    with db_mod.SessionLocal() as s:
        p, _ = build_payload(s, uid, date(2026, 11, 14), night)
    assert p["behavioral_inputs"]["somatic_symptoms"] == ["headache"]
    assert p["behavioral_inputs"]["team_friction_vas"] == 50
    assert p["environmental_logs"]["cabin_ppco2"] == 2.9
    assert p["exercise_log"]["minutes"] == 45

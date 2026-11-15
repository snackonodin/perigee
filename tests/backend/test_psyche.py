"""Psyche 60-item bank: owner-spec scoring, persona at once, context-matched advice,
safety first, per-user isolation, and no effect on load measures."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from backend import db as db_mod
from backend.models import CheckinDaily, SafetyEvent
from backend.services import psyche, surveys
from csi_core.config import PsycheCfg
from tests.backend.test_persona_quiz import _user, client  # noqa: F401  (fixture)

SPEC = json.loads(
    (Path(__file__).resolve().parents[2] / "seeds/instruments/psyche60.json").read_text()
)["psyche_spec"]
CFG = PsycheCfg()


def _answers(default: int = 3, **over: int) -> dict[str, int]:
    a = {f"psyche_{q}": default for q in range(1, 61)}
    for k, v in over.items():
        a[f"psyche_{k.lstrip('q')}"] = v
    return a


def _post(client, h, answers):  # noqa: F811
    body = {"instrument_id": "psyche60", "instrument_version": "1.0",
            "administered_at": "2026-11-15T08:00:00Z", "answers": answers}
    return client.post("/api/v1/responses", json=body, headers=h)


def test_spec_shape() -> None:
    assert sum(len(m["items"]) for m in SPEC["modules"].values()) == 60
    assert len(SPEC["stability"]["raw"]) + len(SPEC["stability"]["inverted"]) == 16
    assert len(SPEC["agency"]["raw"]) + len(SPEC["agency"]["inverted"]) == 12


def test_all_neutral_sits_on_the_midpoint() -> None:
    r = psyche.score(_answers(3), SPEC, CFG)
    assert r["stability"] == 12.0 and r["agency"] == 12.0
    assert r["quadrant"] == "Autonomous Pioneer"  # crossing is inclusive (>= 12)
    assert all(v == 3.0 for v in r["modules"].values())


def test_reverse_items_and_axes() -> None:
    # every stability-raw item 5 and every stability-inverted item 1 -> 20
    a = _answers(3, **{f"q{q}": 5 for q in SPEC["stability"]["raw"]},
                 **{f"q{q}": 1 for q in SPEC["stability"]["inverted"]})
    # make agency low: raw items 1, inverted 5
    a.update({f"psyche_{q}": 1 for q in SPEC["agency"]["raw"]})
    a.update({f"psyche_{q}": 5 for q in SPEC["agency"]["inverted"]})
    r = psyche.score(a, SPEC, CFG)
    assert r["stability"] == 20.0 and r["agency"] == 4.0 and r["quadrant"] == "Steady Anchor"
    # Q4 is reversed inside module 1: raw 5 -> scored 1
    assert psyche.score(_answers(3, q4=5), SPEC, CFG)["modules"]["m1"] == round(16 / 6, 3)


def test_ui_flags() -> None:
    r = psyche.score(_answers(3, q55=4, q59=4, q56=5, q57=4, q58=4, q60=4), SPEC, CFG)
    f = r["flags"]
    assert f["show_raw_telemetry"] and f["calm_non_alarming_tone"]
    assert f["structured_checklist_mode"] and f["baseline_only_framing"]
    assert f["privacy_lock_reminder"]


def test_quiz_gives_persona_at_once_and_hides_module_scores(client) -> None:  # noqa: F811
    _, h = _user("a@example.test")
    res = _post(client, h, _answers(3))
    assert res.status_code == 200 and res.json()["crisis"] is False
    assert "modules" not in json.dumps(res.json())
    j = client.get("/api/v1/persona", headers=h).json()
    assert j["available"] and j["source"] == "psyche60"
    assert j["persona_matrix"]["quadrant_name"] == "Autonomous Pioneer"
    assert "modules" not in json.dumps(j) and j["advice"] == []  # no current signal yet


def _checkin(uid: str, stress: int) -> None:
    with db_mod.SessionLocal() as s:
        s.add(CheckinDaily(user_id=uid, date=datetime.now(UTC).date(), slot="pm",
                           instrument_id="daily_pm", instrument_version="1.0",
                           answers={"mood": 2, "stress": stress, "energy": 2}))
        s.commit()


def test_high_tendency_plus_recent_stress_gives_advice(client) -> None:  # noqa: F811
    uid, h = _user("a@example.test")
    _post(client, h, _answers(3, **{f"q{q}": 5 for q in range(19, 25) if q != 23}, q23=1))
    assert client.get("/api/v1/persona", headers=h).json()["advice"] == []
    _checkin(uid, stress=4)
    tags = [a["tag"] for a in client.get("/api/v1/persona", headers=h).json()["advice"]]
    assert tags == ["autonomy_strain"]


def test_no_advice_while_safety_screen_pending(client) -> None:  # noqa: F811
    uid, h = _user("a@example.test")
    _post(client, h, _answers(3, **{f"q{q}": 5 for q in range(19, 25) if q != 23}, q23=1))
    _checkin(uid, stress=4)
    with db_mod.SessionLocal() as s:
        s.add(SafetyEvent(user_id=uid, source="survey:phq9", reason="safety_item"))
        s.commit()
    assert client.get("/api/v1/persona", headers=h).json()["advice"] == []


def test_user_b_cannot_see_user_a(client) -> None:  # noqa: F811
    _, ha = _user("a@example.test")
    _, hb = _user("b@example.test")
    _post(client, ha, _answers(3))
    assert client.get("/api/v1/persona", headers=hb).json()["available"] is False


def test_not_a_load_measure(client) -> None:  # noqa: F811
    uid, h = _user("a@example.test")
    _post(client, h, _answers(3))
    with db_mod.SessionLocal() as s:
        out = surveys.weekly_indices(s, uid, date(2026, 11, 9))
    assert "psyche60" not in out


def _post_part(client, h, i: int, answers: dict[str, int]):  # noqa: F811
    inst = client.get(f"/api/v1/instruments/psyche_p{i}", headers=h).json()
    body = {"instrument_id": f"psyche_p{i}", "instrument_version": "1.0",
            "administered_at": f"2026-11-15T0{i}:00:00Z",
            "answers": {it["key"]: answers[it["key"]] for it in inst["items"]}}
    return client.post("/api/v1/responses", json=body, headers=h)


def test_five_themed_parts_cover_the_bank_once() -> None:
    seen: list[str] = []
    for i in range(1, 6):
        d = json.loads((Path(__file__).resolve().parents[2]
                        / f"seeds/instruments/psyche_p{i}.json").read_text())
        assert len(d["items"]) == 12
        seen += [it["key"] for it in d["items"]]
    assert sorted(seen) == sorted(f"psyche_{q}" for q in range(1, 61))


def test_parts_one_after_another_give_the_same_persona(client) -> None:  # noqa: F811
    _, h = _user("a@example.test")
    a = _answers(3, q19=5, q20=5, q21=5)
    for i in range(1, 4):
        assert _post_part(client, h, i, a).json()["crisis"] is False
    j = client.get("/api/v1/persona", headers=h).json()
    assert j["available"] is False and len(j["progress"]["done"]) == 3
    for i in (4, 5):
        _post_part(client, h, i, a)
    j = client.get("/api/v1/persona", headers=h).json()
    full = psyche.score(a, SPEC, CFG)
    assert j["available"] and j["source"] == "psyche60"
    assert j["persona_matrix"]["quadrant_name"] == full["quadrant"]
    assert j["persona_matrix"]["agency_score"] == full["agency"]


def test_parts_without_answer_consent_never_build_a_persona(client) -> None:  # noqa: F811
    _, h = _user("a@example.test", consents=False)
    for i in range(1, 6):
        _post_part(client, h, i, _answers(3))
    j = client.get("/api/v1/persona", headers=h).json()
    assert j["available"] is False and j["progress"]["answers_kept"] is False
    assert len(j["progress"]["done"]) == 5


def test_profile_has_five_axes_in_0_1(client) -> None:  # noqa: F811
    _, h = _user("a@example.test")
    _post(client, h, _answers(3, **{f"q{q}": 5 for q in (1, 2, 3, 5, 6)}))
    prof = client.get("/api/v1/persona", headers=h).json()["profile"]
    keys = ["mind_at_rest", "feelings", "people", "focus", "body_feedback"]
    assert [p["key"] for p in prof] == keys
    assert all(0.0 <= p["level"] <= 1.0 for p in prof)
    assert prof[0]["level"] > prof[1]["level"]  # rumination answers raise "Mind at rest"


def test_type_mix_stretches_toward_own_type() -> None:
    mix = {m["type"]: m for m in psyche.type_mix(17.0, 16.0)}
    lv = {t: m["level"] for t, m in mix.items()}
    assert max(lv, key=lv.get) == "Autonomous Pioneer"
    assert lv["Autonomous Pioneer"] > 2 * lv["Steady Anchor"]  # a clear stretch, not a square
    assert lv["Internal Deliberator"] < 0.15  # the opposite corner stays short
    assert abs(sum(m["share"] for m in mix.values()) - 1) < 0.01
    centre = psyche.type_mix(12.0, 12.0)
    assert len({m["level"] for m in centre}) == 1  # midpoint: a small even diamond

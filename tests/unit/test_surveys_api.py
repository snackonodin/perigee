"""Routes: GET /instruments, GET /instruments/{id}, POST /responses, GET /guidance.

POST /responses must always return the safety object: 200 with ok=false for any
invalid input, 500 with the same body if storage fails.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import db as db_mod
from backend.config import get_settings
from backend.main import create_app
from backend.models import (
    Base,
    CheckinDaily,
    Flag,
    GuidanceShown,
    SafetyEvent,
    SurveyResponseRow,
)
from backend.services import accounts, guidance, surveys

PW = "long enough password"


@pytest.fixture
def app_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    d = tmp_path / "astro-data"
    d.mkdir()
    monkeypatch.setenv("DATA_DIR", str(d))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{d / 'db' / 'astro.db'}")
    get_settings.cache_clear()
    eng = db_mod.init_db()  # file DB: TestClient runs sync routes in worker threads
    Base.metadata.create_all(eng)
    with db_mod.SessionLocal() as s:
        surveys.load_catalog(s)
        guidance.load_guidance_cards(s)
    yield
    eng.dispose()
    db_mod.SessionLocal.configure(bind=None)
    get_settings.cache_clear()


@pytest.fixture
def client(app_db) -> Iterator[TestClient]:
    app = create_app(with_lifespan=False)
    assert {
        "backend.api.v1.instruments",
        "backend.api.v1.responses",
        "backend.api.v1.guidance",
    } <= set(app.state.mounted)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _user(email: str, consents: bool = True) -> tuple[str, dict[str, str]]:
    with db_mod.SessionLocal() as s:
        r = accounts.signup(s, email, PW)
        if consents:
            accounts.set_consents(s, r.user_id, {"survey_answers": True, "checkins": True}, "t1")
    return r.user_id, {"Authorization": f"Bearer {r.access_token}"}


@pytest.fixture
def auth(client) -> tuple[str, dict[str, str]]:
    return _user("a@example.test")


def _phq9(item9: int, rest: int = 0) -> dict[str, int]:
    a = {f"phq9_{i}": rest for i in range(1, 9)}
    a["phq9_9"] = item9
    return a


def _post(client, headers, instrument="phq9", answers=None, version="1.0", **extra):
    body = {
        "instrument_id": instrument,
        "instrument_version": version,
        "administered_at": "2026-11-10T08:00:00Z",
        "answers": answers,
        **extra,
    }
    return client.post("/api/v1/responses", json=body, headers=headers)


def _count(model) -> int:
    with db_mod.SessionLocal() as s:
        return s.query(model).count()


# --------------------------------------------------------------------------- auth


def test_all_routes_require_auth(client) -> None:
    assert client.get("/api/v1/instruments").status_code == 401
    assert client.get("/api/v1/instruments/phq9").status_code == 401
    assert client.get("/api/v1/guidance?flag_id=x").status_code == 401
    r = client.post("/api/v1/responses", json={"instrument_id": "phq9", "answers": {}})
    assert r.status_code == 401 and r.json()["error"] == "unauthorized"


# --------------------------------------------------------------------------- instruments


def test_list_and_get_instruments(client, auth) -> None:
    _, h = auth
    lst = client.get("/api/v1/instruments", headers=h).json()
    assert {i["id"] for i in lst} == {
        "phq2", "gad2", "who5", "phq9", "daily_am", "daily_pm", "mini_ipip", "psyche60",
        "body_cabin", "psyche_p1", "psyche_p2", "psyche_p3", "psyche_p4", "psyche_p5",
    }
    phq9 = next(i for i in lst if i["id"] == "phq9")
    assert phq9["items"] == 9 and phq9["source_url"].startswith("https://")
    full = client.get("/api/v1/instruments/phq9", headers=h).json()
    assert full["items"][8]["safety_trigger"] == {"min_value": 1}
    r = client.get("/api/v1/instruments/nope", headers=h)
    assert r.status_code == 404 and r.json() == {
        "error": "not_found",
        "message": "unknown instrument",
    }


# --------------------------------------------------------------------------- responses


def test_valid_response_scored_and_stored(client, auth) -> None:
    _, h = auth
    r = _post(client, h, "who5", {f"who5_{i}": 4 for i in range(1, 6)})
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True and j["stored"] is True and j["id"]
    assert j["total"] == 20 and j["scores"]["score"] == 80
    assert j["safety"] == {"show": False, "reason": None, "resources": []}


def test_item9_positive_returns_safety(client, auth) -> None:
    _, h = auth
    j = _post(client, h, answers=_phq9(1)).json()
    assert j["ok"] is True and j["safety"]["show"] is True
    assert any("flight surgeon" in x for x in j["safety"]["resources"])
    assert _count(SafetyEvent) == 1


@pytest.mark.parametrize(
    "answers, extra",
    [
        ({"phq9_9": 2}, {}),  # missing items
        ({**_phq9(1), "phq9_3": 7}, {}),  # out-of-range option on another item
        ({**_phq9(0), "phq9_9": "often"}, {}),  # non-numeric value on the safety item
        (_phq9(1), {"administered_at": "2026-11-10T08:00:00"}),  # naive timestamp
        (_phq9(3), {"instrument_version": "9.9"}),  # unknown version
    ],
)
def test_invalid_input_still_returns_safety_200(client, auth, answers, extra) -> None:
    _, h = auth
    r = _post(client, h, answers=answers, **extra)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is False and j["error"] == "invalid" and j["errors"]
    assert j["safety"]["show"] is True and j["safety"]["resources"]
    assert j["id"] is None and j["stored"] is False
    assert _count(SafetyEvent) == 1 and _count(SurveyResponseRow) == 0
    # errors name keys or fields, never the submitted values
    assert "often" not in str(j["errors"])
    assert not any(e.endswith((" 7", ": 7", "=7")) for e in j["errors"])


def test_unknown_instrument_is_200_with_safety_false(client, auth) -> None:
    _, h = auth
    j = _post(client, h, "nope", {"x": 1}).json()
    assert j["ok"] is False and j["error"] == "unknown_instrument"
    assert j["safety"]["show"] is False


def test_storage_failure_is_500_with_safety(client, auth, monkeypatch) -> None:
    _, h = auth

    def fail(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(surveys, "_store_survey", fail)
    r = _post(client, h, answers=_phq9(2))
    assert r.status_code == 500
    j = r.json()
    assert j["ok"] is False and j["error"] == "storage" and j["safety"]["show"] is True
    assert _count(SafetyEvent) == 1


def test_user_comes_from_token_not_body(client, auth) -> None:
    uid, h = auth
    other, _ = _user("b@example.test")
    j = _post(client, h, "phq2", {"phq2_1": 1, "phq2_2": 1}, user_id=other).json()
    assert j["ok"] is True
    with db_mod.SessionLocal() as s:
        assert s.get(SurveyResponseRow, j["id"]).user_id == uid


def test_checkin_without_consent_not_stored(client) -> None:
    _, h = _user("c@example.test", consents=False)
    j = _post(client, h, "daily_am", {"sleep_quality": 3, "energy": 2, "mood": 3}).json()
    assert j["ok"] is True and j["stored"] is False and j["id"] is None
    assert j["scores"]["items"] == {"sleep_quality": 3, "energy": 2, "mood": 3}


def test_no_answer_values_in_logs(client, auth, caplog) -> None:
    _, h = auth
    sa = logging.getLogger("sqlalchemy.engine")
    old = sa.level
    sa.setLevel(logging.INFO)
    try:
        with caplog.at_level(logging.DEBUG):
            _post(client, h, answers=_phq9(2, rest=3))
            _post(client, h, answers={"phq9_9": "often", "phq9_1": 9})
    finally:
        sa.setLevel(old)
    blob = "\n".join(r.getMessage() + repr(r.args) for r in caplog.records)
    assert caplog.records
    assert "phq9_" not in blob and "often" not in blob


# --------------------------------------------------------------------------- guidance


def _flag(user_id: str, state: str, components: dict) -> str:
    from datetime import date

    with db_mod.SessionLocal() as s:
        f = Flag(
            user_id=user_id,
            date=date(2026, 11, 10),
            domain_pair="physiology|mental",
            phys_level=int(state != "mental_only"),
            mental_level=int(state != "phys_only"),
            state=state,
            priority=1.0,
            components=components,
            message_key=f"flag.{state}",
        )
        s.add(f)
        s.commit()
        return f.id


def test_guidance_for_own_flag(client, auth) -> None:
    uid, h = auth
    fid = _flag(
        uid, "mental_only", {"mental": {"phq2": {"band": {"band": "x"}}}, "alert_robust_z": 2.5}
    )
    r = client.get("/api/v1/guidance", params={"flag_id": fid}, headers=h)
    assert r.status_code == 200
    cards = r.json()
    assert cards[0]["card_key"] == "talk_to_support"
    assert all(c["contact_support_text"] and c["reviewed_by"] is None for c in cards)
    assert _count(GuidanceShown) == len(cards)


def test_guidance_other_users_flag_is_404(client, auth) -> None:
    _, h = auth
    other, _ = _user("d@example.test")
    fid = _flag(
        other, "mental_only", {"mental": {"phq2": {"band": {"band": "x"}}}, "alert_robust_z": 2.5}
    )
    r = client.get("/api/v1/guidance", params={"flag_id": fid}, headers=h)
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    assert _count(GuidanceShown) == 0
    assert client.get("/api/v1/guidance", headers=h).status_code == 422  # flag_id required


def test_missing_version_uses_catalog_current(client, auth) -> None:
    _, h = auth
    body = {"instrument_id": "phq9", "answers": _phq9(1)}
    j = client.post("/api/v1/responses", json=body, headers=h).json()
    assert j["ok"] is True and j["stored"] is True
    assert j["safety"]["show"] is True
    with db_mod.SessionLocal() as s:
        assert s.get(SurveyResponseRow, j["id"]).instrument_version == "1.0"


def test_missing_version_invalid_answers_still_safety(client, auth) -> None:
    _, h = auth
    j = client.post(
        "/api/v1/responses", json={"instrument_id": "phq9", "answers": {"phq9_9": 2}}, headers=h
    ).json()
    assert j["ok"] is False and j["error"] == "invalid" and j["safety"]["show"] is True
    assert _count(SafetyEvent) == 1


# --------------------------------------------------------------------------- answers_retained


@pytest.mark.parametrize("survey_answers", [True, False])
@pytest.mark.parametrize("checkins", [True, False])
@pytest.mark.parametrize(
    "instrument, answers",
    [
        ("phq2", {"phq2_1": 1, "phq2_2": 2}),
        ("daily_pm", {"mood": 2, "stress": 1, "energy": 3}),
    ],
)
def test_answers_retained_matches_consent_and_db(
    client, instrument, answers, survey_answers, checkins
) -> None:
    uid, h = _user(f"r-{instrument}-{survey_answers}-{checkins}@example.test", consents=False)
    with db_mod.SessionLocal() as s:
        accounts.set_consents(
            s, uid, {"survey_answers": survey_answers, "checkins": checkins}, "t1"
        )
    j = _post(client, h, instrument, answers).json()
    assert j["ok"] is True
    if instrument == "phq2":
        assert j["stored"] is True
        assert j["answers_retained"] is survey_answers
        with db_mod.SessionLocal() as s:
            row = s.get(SurveyResponseRow, j["id"])
            assert (row.answers is not None) is j["answers_retained"]
    else:
        assert j["stored"] is checkins and j["answers_retained"] is checkins
        with db_mod.SessionLocal() as s:
            assert (s.get(CheckinDaily, j["id"]) is not None) if checkins else j["id"] is None


def test_answers_retained_false_on_invalid_and_storage_error(client, auth, monkeypatch) -> None:
    _, h = auth
    assert _post(client, h, answers={"phq9_9": 1}).json()["answers_retained"] is False

    def fail(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(surveys, "_store_survey", fail)
    r = _post(client, h, answers=_phq9(0))
    assert r.status_code == 500 and r.json()["answers_retained"] is False

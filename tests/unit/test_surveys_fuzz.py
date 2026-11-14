"""FUZZ-1: property tests through the real API (create_app), deterministic, 200+ examples.

1. Every POST /responses (random instrument, answers, missing items, wrong types,
   versions, timestamps) returns a safety object; PHQ-9 item 9 >= 1 => show=true, and
   exactly one safety_event is written per shown safety screen.
2. Random users and data: no list route ever returns another user's rows.
3. Random consent states: storage follows consent exactly.
4. No answer values or item keys appear in captured logs.

One app + DB per module (signup uses Argon2, too slow per example); assertions use
per-example deltas, so the accumulated state is part of what is being fuzzed.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from backend import db as db_mod
from backend.config import get_settings
from backend.main import create_app
from backend.models import (
    Base,
    CheckinDaily,
    Flag,
    NightFeaturesRow,
    SafetyEvent,
    SurveyResponseRow,
)
from backend.services import accounts, guidance, readouts, surveys

FUZZ = settings(
    max_examples=200,
    derandomize=True,  # deterministic: same examples every run, whatever pytest-randomly does
    deadline=None,
    database=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
        HealthCheck.data_too_large,
    ],
)
PW = "long enough password"
CATALOG = surveys.load_seed_catalog()
ITEM_KEYS = {it["key"] for inst in CATALOG.values() for it in inst["items"]}
N_USERS = 3


@dataclass
class World:
    client: TestClient
    users: list[tuple[str, dict[str, str]]]  # (user_id, auth headers)
    owner: dict[str, str] = field(default_factory=dict)  # row id -> user_id


@pytest.fixture(scope="module")
def world(tmp_path_factory) -> Iterator[World]:
    mp = pytest.MonkeyPatch()
    d = tmp_path_factory.mktemp("fuzz") / "astro-data"
    d.mkdir()
    mp.setenv("DATA_DIR", str(d))
    mp.setenv("DATABASE_URL", f"sqlite:///{d / 'db' / 'astro.db'}")
    get_settings.cache_clear()
    eng = db_mod.init_db()
    Base.metadata.create_all(eng)
    users = []
    with db_mod.SessionLocal() as s:
        surveys.load_catalog(s)
        guidance.load_guidance_cards(s)
        for i in range(N_USERS):
            r = accounts.signup(s, f"fuzz{i}@example.test", PW)
            accounts.set_consents(s, r.user_id, {"survey_answers": True, "checkins": True}, "v1")
            users.append((r.user_id, {"Authorization": f"Bearer {r.access_token}"}))
    try:
        with TestClient(create_app(with_lifespan=False), raise_server_exceptions=False) as c:
            yield World(client=c, users=users)
    finally:
        eng.dispose()
        db_mod.SessionLocal.configure(bind=None)
        mp.undo()
        get_settings.cache_clear()


def _count(model, user_id: str, *where) -> int:
    with db_mod.SessionLocal() as s:
        return s.scalar(
            select(func.count()).select_from(model).where(model.user_id == user_id, *where)
        )


def _set_consents(w: World, i: int, **scopes: bool) -> None:
    r = w.client.put(
        "/api/v1/me/consents",
        headers=w.users[i][1],
        json={"scopes": scopes, "policy_version": "v1"},
    )
    assert r.status_code == 200, r.text


# --------------------------------------------------------------------------- strategies

JUNK = st.one_of(
    st.integers(-5, 12),
    st.text(max_size=6),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.none(),
    st.booleans(),
    st.lists(st.integers(-1, 4), max_size=2),
    st.dictionaries(st.text(max_size=2), st.integers(), max_size=1),
)


@st.composite
def payloads(draw) -> dict[str, Any]:
    inst_id = draw(st.sampled_from([*CATALOG, "nope", "PHQ9", "x" * 32]))
    inst = CATALOG.get(inst_id)
    answers: dict[str, Any] = {}
    for it in inst["items"] if inst else []:
        if draw(st.integers(0, 9)) == 0:
            continue  # missing item
        valid = st.sampled_from([o["value"] for o in it["options"]])
        answers[it["key"]] = draw(st.one_of(valid, valid, valid, JUNK))  # mostly valid
    answers.update(draw(st.dictionaries(st.text(min_size=1, max_size=8), JUNK, max_size=2)))
    if draw(st.booleans()):  # aim at the safety item, whatever the instrument
        answers["phq9_9"] = draw(st.one_of(st.integers(0, 3), JUNK))
    body: dict[str, Any] = {"instrument_id": inst_id, "answers": answers}
    if draw(st.booleans()):
        body["instrument_version"] = draw(
            st.one_of(st.just("1.0"), st.none(), st.text(max_size=4), st.integers(), st.booleans())
        )
    if draw(st.booleans()):
        body["administered_at"] = draw(
            st.one_of(
                st.just("2026-11-10T08:00:00Z"),
                st.just("2026-11-10T08:00:00"),  # naive
                st.text(max_size=8),
                st.integers(-(10**6), 2 * 10**9),
                st.none(),
            )
        )
    return body


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


# --------------------------------------------------------------------------- 1. safety


@FUZZ
@given(body=payloads(), who=st.integers(0, N_USERS - 1))
def test_every_response_carries_safety_and_one_event(world: World, body, who) -> None:
    uid, h = world.users[who]
    before = _count(SafetyEvent, uid)
    r = world.client.post("/api/v1/responses", json=body, headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    safety = j["safety"]
    assert isinstance(safety["show"], bool) and isinstance(safety["resources"], list)
    assert bool(safety["resources"]) == safety["show"]
    assert _count(SafetyEvent, uid) - before == (1 if safety["show"] else 0)

    item9 = body["answers"].get("phq9_9", None) if body["instrument_id"] == "phq9" else None
    if body["instrument_id"] == "phq9" and _is_int(item9) and item9 >= 1:
        assert safety["show"] is True, body
    # body_cabin red flags (sudden chest pain, fainting, severe breathlessness) are safety
    # items too: any present red flag >= 1 must show the screen.
    red = {k: v for k, v in body["answers"].items() if str(k).startswith("red_")} \
        if body["instrument_id"] == "body_cabin" else {}
    def _fires(v: Any) -> bool:  # same rule as surveys.safety_check: >= 1, or uncomparable
        try:
            return bool(v >= 1)
        except TypeError:
            return True

    if any(_fires(v) for v in red.values()):
        assert safety["show"] is True, body
    elif body["instrument_id"] != "phq9" or "phq9_9" not in body["answers"]:
        assert safety["show"] is False, body
    if body["instrument_id"] == "phq9" and _is_int(item9) and item9 == 0:
        assert safety["show"] is False, body


# --------------------------------------------------------------------------- 2. isolation

ACTION = st.tuples(
    st.sampled_from(["checkin", "survey", "night", "flag"]),
    st.integers(0, N_USERS - 1),
    st.integers(0, 20),  # days ago
    st.integers(0, 4),  # option value / variant
)


def _apply(w: World, kind: str, who: int, ago: int, v: int) -> None:
    uid, h = w.users[who]
    day = readouts.utc_today() - timedelta(days=ago)
    at = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=9)
    if kind == "checkin":
        slot = "daily_am" if v % 2 else "daily_pm"
        answers = {it["key"]: v for it in CATALOG[slot]["items"]}
        body = {"instrument_id": slot, "answers": answers, "administered_at": at.isoformat()}
        j = w.client.post("/api/v1/responses", json=body, headers=h).json()
        assert j["ok"] and j["id"]
        w.owner[j["id"]] = uid
        return
    if kind == "survey":
        body = {
            "instrument_id": "phq2",
            "answers": {"phq2_1": v % 4, "phq2_2": 0},
            "administered_at": at.isoformat(),
        }
        j = w.client.post("/api/v1/responses", json=body, headers=h).json()
        assert j["ok"] and j["id"]
        w.owner[j["id"]] = uid
        return
    with db_mod.SessionLocal() as s:
        if kind == "night":
            sk = "csi" if v % 2 else "synthetic"
            exists = s.scalar(
                select(NightFeaturesRow.id).where(
                    NightFeaturesRow.user_id == uid,
                    NightFeaturesRow.date == day,
                    NightFeaturesRow.source_kind == sk,
                )
            )
            if exists:
                return
            row = NightFeaturesRow(
                user_id=uid,
                date=day,
                presence_hours=float(v),
                valid=True,
                session_ids=[f"sess-{uid}"],
                source_kind=sk,
            )
        else:
            row = Flag(
                user_id=uid,
                date=day,
                domain_pair="physiology|mental",
                phys_level=0,
                mental_level=1,
                state="mental_only",
                priority=float(v),
                components={"mental": {"phq2": {"band": {"band": "x"}}}, "alert_robust_z": 2.5},
                message_key="flag.mental_only",
            )
        s.add(row)
        s.commit()
        w.owner[row.id] = uid


def _ids(rows: list[dict]) -> set[str]:
    return {r["id"] for r in rows}


@FUZZ
@given(actions=st.lists(ACTION, min_size=1, max_size=6))
def test_no_list_route_returns_another_users_rows(world: World, actions) -> None:
    for a in actions:
        _apply(world, *a)
    today = readouts.utc_today()
    rng = {"from": (today - timedelta(days=30)).isoformat(), "to": today.isoformat()}
    for uid, h in world.users:
        c = world.client
        got: set[str] = set()
        got |= _ids(c.get("/api/v1/nights", params=rng, headers=h).json())
        got |= _ids(c.get("/api/v1/flags", params={"since": rng["from"]}, headers=h).json())
        got |= _ids(c.get("/api/v1/checkins", params=rng, headers=h).json())
        t = c.get("/api/v1/today", headers=h).json()
        if t["latest_night"]:
            got.add(t["latest_night"]["id"])
        got |= _ids(t["flags"])
        foreign = {i for i in got if world.owner.get(i, uid) != uid}
        assert not foreign, f"user {uid} received another user's rows"
        idx = c.get("/api/v1/indices", headers=h).json()
        with db_mod.SessionLocal() as s:
            expect = surveys.weekly_indices(s, uid, readouts.week_start(None))
        assert json.loads(json.dumps(expect)) == idx["indices"]


# --------------------------------------------------------------------------- 3. consent


@st.composite
def valid_submission(draw) -> dict[str, Any]:
    inst_id = draw(st.sampled_from(list(CATALOG)))
    answers = {
        it["key"]: draw(st.sampled_from([o["value"] for o in it["options"]]))
        for it in CATALOG[inst_id]["items"]
    }
    when = draw(
        st.datetimes(
            min_value=datetime(2000, 1, 1), max_value=datetime(2099, 1, 1), timezones=st.just(UTC)
        )
    )
    return {"instrument_id": inst_id, "answers": answers, "administered_at": when.isoformat()}


@FUZZ
@given(
    sub=valid_submission(),
    who=st.integers(0, N_USERS - 1),
    survey_answers=st.booleans(),
    checkins=st.booleans(),
)
def test_storage_follows_consent_exactly(world: World, sub, who, survey_answers, checkins) -> None:
    uid, h = world.users[who]
    _set_consents(world, who, survey_answers=survey_answers, checkins=checkins)
    try:
        inst_id = sub["instrument_id"]
        is_checkin = inst_id in surveys.CHECKIN_SLOTS
        day = datetime.fromisoformat(sub["administered_at"]).date()
        slot = surveys.CHECKIN_SLOTS.get(inst_id)
        where = (CheckinDaily.date == day, CheckinDaily.slot == slot)
        ck_before = _count(CheckinDaily, uid, *where) if is_checkin else 0
        sr_before = _count(SurveyResponseRow, uid)

        j = world.client.post("/api/v1/responses", json=sub, headers=h).json()
        assert j["ok"] is True, j

        if is_checkin:
            assert _count(SurveyResponseRow, uid) == sr_before  # never in survey_responses
            assert j["stored"] is checkins and j["answers_retained"] is checkins
            if checkins:
                assert _count(CheckinDaily, uid, *where) == 1
                with db_mod.SessionLocal() as s:
                    row = s.get(CheckinDaily, j["id"])
                    assert row.user_id == uid and row.answers == sub["answers"]
            else:
                assert j["id"] is None
                assert _count(CheckinDaily, uid, *where) == ck_before  # nothing written
        else:
            assert j["stored"] is True and _count(SurveyResponseRow, uid) == sr_before + 1
            with db_mod.SessionLocal() as s:
                row = s.get(SurveyResponseRow, j["id"])
                assert row.user_id == uid
                assert j["answers_retained"] is survey_answers
                if survey_answers:
                    assert row.answers == sub["answers"] and row.answers_hmac is None
                else:
                    assert row.answers is None
                    assert row.answers_hmac == surveys.answers_digest(sub["answers"])
                    assert "items" not in (row.scores or {})
    finally:
        _set_consents(world, who, survey_answers=True, checkins=True)


# --------------------------------------------------------------------------- 4. logs

MARK = st.text(alphabet="abcdefghij", min_size=4, max_size=8).map(lambda s: f"zq{s}")


@st.composite
def marked_payloads(draw) -> tuple[dict[str, Any], set[str]]:
    """A payload whose free-form keys/values carry unique markers, plus the needles."""
    body = draw(payloads())
    needles = {k for k in body["answers"] if k in ITEM_KEYS}
    for _ in range(draw(st.integers(0, 2))):
        k, v = draw(MARK), draw(MARK)
        body["answers"][k] = v
        needles |= {k, v}
    return body, needles


@FUZZ
@given(case=marked_payloads(), who=st.integers(0, N_USERS - 1))
def test_no_answer_values_or_item_keys_in_logs(world: World, caplog, case, who) -> None:
    body, needles = case
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        world.client.post("/api/v1/responses", json=body, headers=world.users[who][1])
    text = "\n".join(
        f"{r.name} {r.getMessage()} {r.args!r} {r.exc_text or ''}" for r in caplog.records
    )
    leaked = sorted(n for n in needles if n in text)
    assert not leaked, f"answer keys/values in logs: {leaked}"


def test_profile_is_deterministic_and_large_enough() -> None:
    assert FUZZ.max_examples >= 200 and FUZZ.derandomize is True

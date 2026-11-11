"""Read routes (nights, flags, indices, checkins, today): A/B isolation and /today shape."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from backend import db as db_mod
from backend.main import create_app
from backend.models import Baseline, CheckinDaily, Flag, GuidanceShown, NightFeaturesRow
from backend.services import readouts
from tests.unit.test_surveys_api import _user, app_db  # noqa: F401  (fixture reuse)


@pytest.fixture
def client(app_db):  # noqa: F811
    with TestClient(create_app(with_lifespan=False), raise_server_exceptions=False) as c:
        yield c


def _seed(uid: str) -> str:
    today = readouts.utc_today()
    with db_mod.SessionLocal() as s:
        s.add(
            NightFeaturesRow(
                user_id=uid,
                date=today - timedelta(days=1),
                presence_hours=7.0,
                rr_med=14.0,
                hr_med=61.0,
                valid=True,
                quality=0.9,
                session_ids=["s1"],
                source_kind="synthetic",
            )
        )
        f = Flag(
            user_id=uid,
            date=today,
            domain_pair="physiology|mental",
            phys_level=0,
            mental_level=1,
            state="mental_only",
            priority=1.0,
            message_key="flag.mental_only",
            components={"mental": {"phq2": {"band": {"band": "x"}}}, "alert_robust_z": 2.5},
        )
        s.add(f)
        s.add(
            CheckinDaily(
                user_id=uid,
                date=today,
                slot="am",
                instrument_id="daily_am",
                instrument_version="1.0",
                answers={"mood": 2},
            )
        )
        s.add(Baseline(user_id=uid, feature="rr_med", n=3, window_days=28, maturity="warm_up"))
        s.commit()
        return f.id


ROUTES = ["/api/v1/nights", "/api/v1/flags", "/api/v1/checkins", "/api/v1/indices", "/api/v1/today"]


@pytest.mark.parametrize("path", ROUTES)
def test_requires_auth(client, path) -> None:
    assert client.get(path).status_code == 401


def test_user_a_cannot_read_user_b(client) -> None:
    _, ha = _user("a@example.test")
    ub, hb = _user("b@example.test")
    _seed(ub)
    day = (readouts.utc_today() - timedelta(days=1)).isoformat()
    for path in ("/api/v1/nights", "/api/v1/flags", "/api/v1/checkins"):
        assert client.get(path, headers=ha).json() == [], path
        assert client.get(path, headers=hb).json(), path
    assert client.get(f"/api/v1/nights/{day}", headers=ha).status_code == 404
    assert client.get(f"/api/v1/nights/{day}", headers=hb).status_code == 200
    t = client.get("/api/v1/today", headers=ha).json()
    assert t["latest_night"] is None and t["flags"] == [] and t["baselines"] == []
    assert client.get("/api/v1/indices", headers=ha).json()["indices"] == {}


def test_today_view(client) -> None:
    uid, h = _user("c@example.test")
    fid = _seed(uid)
    t = client.get("/api/v1/today", headers=h).json()
    n = t["latest_night"]
    assert n["inputs"] == {"session_ids": ["s1"]} and "run_id" in n and "hr_med" not in n
    assert [f["id"] for f in t["flags"]] == [fid]
    assert (
        t["flags"][0]["components"]
        and t["flags"][0]["guidance"][0]["card_key"] == "talk_to_support"
    )
    assert [p["slot"] for p in t["pending_checkins"]] == ["pm"]
    assert t["baselines"][0]["maturity"] == "warm_up"
    assert t["sync_status"] == {"state": "offline"}
    with db_mod.SessionLocal() as s:
        assert s.query(GuidanceShown).count() == len(t["flags"][0]["guidance"])


def test_bad_range_is_400(client) -> None:
    _, h = _user("d@example.test")
    r = client.get("/api/v1/nights", params={"from": "2026-11-10", "to": "2026-11-01"}, headers=h)
    assert r.status_code == 400 and r.json()["error"] == "invalid_range"


def test_openapi_has_typed_schemas(client) -> None:
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    for name in (
        "NightOut",
        "FlagOut",
        "IndicesOut",
        "IndexOut",
        "CheckinOut",
        "TodayOut",
        "TodayFlagOut",
        "BaselineOut",
        "PendingCheckin",
    ):
        assert name in schemas, name
    assert "hr_med" not in schemas["NightOut"]["properties"]
    paths = spec["paths"]
    ok = lambda p: paths[p]["get"]["responses"]["200"]["content"]["application/json"]["schema"]  # noqa: E731
    assert ok("/api/v1/today") == {"$ref": "#/components/schemas/TodayOut"}
    assert ok("/api/v1/indices") == {"$ref": "#/components/schemas/IndicesOut"}
    assert ok("/api/v1/nights")["items"] == {"$ref": "#/components/schemas/NightOut"}


def test_today_reload_does_not_recount_guidance(client) -> None:
    uid, h = _user("e@example.test")
    _seed(uid)
    first = client.get("/api/v1/today", headers=h).json()
    client.get("/api/v1/today", headers=h)
    client.get("/api/v1/today", headers=h)
    with db_mod.SessionLocal() as s:
        assert s.query(GuidanceShown).count() == len(first["flags"][0]["guidance"])

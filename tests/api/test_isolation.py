"""FR15 isolation: user B's token can never read or change user A's rows.

Runs against the real app (backend.main.create_app), so every mounted router is in scope.

To cover a new route, add an IsolationCase to ISOLATION_CASES:
- path may use {a_user_id} or {a_session_id} (A's resources seeded in ``world``).
  Add more ids to ``world`` when a route needs them, e.g. a survey response id.
- expect = the status B must get. Routes on B's own data ("/me") expect 2xx;
  routes that address A's resource by id must expect 404 (not 403: don't confirm it exists).
test_every_route_has_a_case fails until each mounted route has a case or is in EXEMPT.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.main import create_app
from backend.models import (
    Base,
    Baseline,
    CheckinDaily,
    Flag,
    NightFeaturesRow,
    SafetyEvent,
    UserOwned,
    scoped,
)
from backend.services import accounts as acc
from backend.services import jobs, surveys
from backend.services import sessions as sessions_svc
from backend.services.ingestion import ingest_session
from csi_core.synth import synth_night

PW = "long enough password"
A_NAME = "Alice Isolation-Marker"


@dataclass(frozen=True)
class IsolationCase:
    method: str
    path: str  # route template as in OpenAPI, ids filled from ``world``
    expect: int
    json: dict[str, Any] | None = None
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.method.upper()} {self.path}"


ISOLATION_CASES: list[IsolationCase] = [
    # accounts: /me always means the caller, so B gets B's data and A's stays untouched
    IsolationCase("get", "/api/v1/me", 200),
    # public demo sign-in: off in tests (DEMO_ACCESS unset) -> 404, touches nothing of A
    IsolationCase("post", "/api/v1/auth/demo", 404),
    # aggregate demo counts only (no user data); off in tests -> 404
    IsolationCase("get", "/api/v1/demo/stats", 404),
    IsolationCase("patch", "/api/v1/me", 200, json={"display_name": "Bob"}),
    IsolationCase("get", "/api/v1/me/consents", 200),
    IsolationCase(
        "put",
        "/api/v1/me/consents",
        200,
        json={"scopes": {"checkins": False, "raw_csi": False}, "policy_version": "v1"},
    ),
    IsolationCase("post", "/api/v1/me/export", 200),
    IsolationCase("delete", "/api/v1/me", 204),
    # surveys: the instrument catalog is global; responses are written for the caller only
    IsolationCase("get", "/api/v1/instruments", 200),
    IsolationCase("get", "/api/v1/instruments/{instrument_id}", 200),
    IsolationCase(
        "post",
        "/api/v1/responses",
        200,
        json={
            "instrument_id": "phq2",
            "instrument_version": "1.0",
            "answers": {"phq2_1": 0, "phq2_2": 1},
        },
    ),
    # guidance: addressing A's flag by id must look exactly like a missing flag
    IsolationCase("get", "/api/v1/guidance", 404, params={"flag_id": "{a_flag_id}"}),
    # sessions / jobs (db-ingest): lists are B's own (empty); A's ids look missing
    IsolationCase(
        "get",
        "/api/v1/sessions",
        200,
        params={"from": "2026-10-01T00:00:00Z", "to": "2026-12-01T00:00:00Z"},
    ),
    IsolationCase("get", "/api/v1/sessions/{session_id}", 404),
    IsolationCase("get", "/api/v1/windows", 404, params={"session_id": "{a_session_id}"}),
    # per-user inbox: A's folder name does not exist in B's inbox
    IsolationCase("post", "/api/v1/sessions", 400, json={"src_dir": "night_a"}),
    IsolationCase(
        "post",
        "/api/v1/jobs/process",
        404,
        json={"kind": "process_session", "params": {"session_id": "{a_session_id}"}},
    ),
    IsolationCase("get", "/api/v1/jobs/{job_id}", 404),
    # live SSE (db-ingest): replaying A's session must look like a missing session. The
    # plain live stream only ever reads the caller's rows (tested in tests/db/test_live.py).
    IsolationCase("get", "/api/v1/live/vitals", 404, params={"replay_session": "{a_session_id}"}),
    # readouts (surveys, SUR-8): lists and /today are B's own (empty); A's night date is missing
    IsolationCase("get", "/api/v1/nights", 200, params={"from": "2026-10-01", "to": "2026-12-01"}),
    IsolationCase("get", "/api/v1/nights/{day}", 404),
    IsolationCase("get", "/api/v1/flags", 200, params={"since": "2026-10-01"}),
    IsolationCase("get", "/api/v1/indices", 200),  # this week: A's response is in it
    IsolationCase(
        "get", "/api/v1/checkins", 200, params={"from": "2026-10-01", "to": "2026-12-01"}
    ),
    IsolationCase("get", "/api/v1/today", 200),
    # persona: always the caller's own traits (A's quiz never reaches B; test_persona_quiz)
    IsolationCase("get", "/api/v1/persona", 200),
    # pet bubble: built only from the caller's own night and persona (test_pet_dialogue)
    IsolationCase("get", "/api/v1/pet/bubble", 200),
    # injection (INJ-1): estimates for A's session must look like a missing session, write
    # nothing and reveal nothing, whatever else the request carries
    # monitor (on-demand ESP sessions): B's list is B's own; A's session ids look missing.
    # Starting a session never touches A; with no receiver configured in tests it is 503.
    IsolationCase("get", "/api/v1/monitor/sessions", 200),
    IsolationCase("get", "/api/v1/monitor/modes", 200),  # config timings, no user data
    IsolationCase("post", "/api/v1/monitor/sessions", 503, json={"mode": "heart_rate"}),
    IsolationCase("get", "/api/v1/monitor/sessions/{session_id}", 404,
                  params={"show_rates": "true"}),
    IsolationCase("post", "/api/v1/monitor/sessions/{session_id}/stop", 404),
    # real ESP32 captures: demo (synthetic) accounts only; B is a real account, so an empty
    # list and no download. Never A's data either way (shared seed files, not user rows).
    IsolationCase("get", "/api/v1/monitor/samples", 200),
    IsolationCase("get", "/api/v1/monitor/samples/{sample_id}/capture.csv", 404),
    IsolationCase(
        "post",
        "/api/v1/ingest/estimates",
        404,
        json={
            "session_id": "{a_session_id}",
            "windows": [
                {
                    "t_start": "2026-11-01T23:00:00+00:00",
                    "t_end": "2026-11-01T23:01:00+00:00",
                    "rr_a": 14.0,
                    "rr_b": 14.0,
                }
            ],
        },
    ),
]

# Routes that serve no per-user data. Anything else must have a case.
EXEMPT: set[tuple[str, str]] = {
    ("get", "/api/v1/health"),
    ("get", "/api/v1/version"),
    ("post", "/api/v1/auth/signup"),
    ("post", "/api/v1/auth/login"),
    ("post", "/api/v1/auth/refresh"),  # possession of the refresh token is the credential
    ("post", "/api/v1/auth/logout"),
}


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def app_client(engine, monkeypatch):
    """The real app, minus the lifespan (the test DB is already bound by ``engine``).

    Tokens live 4 h here: the ``world`` fixture seeds a lot of data and, on a loaded machine,
    can take longer than the default 15-minute access token (overnight run 2026-11-14 hit
    401 "invalid or expired token"). Expiry itself is tested in the accounts tests.
    """
    from backend.config import get_settings

    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "240")
    get_settings.cache_clear()
    with TestClient(create_app(with_lifespan=False), raise_server_exceptions=False) as c:
        yield c


def _signup(c: TestClient, email: str) -> dict[str, str]:
    res = c.post("/api/v1/auth/signup", json={"email": email, "password": PW})
    assert res.status_code == 201, res.text
    return res.json()


def _h(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _night(out: Path) -> Path:
    synth_night(
        out,
        start_utc=datetime(2026, 11, 1, 22, 0, tzinfo=UTC),
        hours=0.05,
        rr_bpm=14.0,
        motion_bursts=0,
        seed=7,
    )
    return out


@pytest.fixture
def world(app_client, db, tmp_path) -> dict[str, Any]:
    """A with data in as many tables as exist today; B with an account and nothing else."""
    a = _signup(app_client, "alice@example.com")
    b = _signup(app_client, "bob@example.com")
    app_client.patch("/api/v1/me", headers=_h(a), json={"display_name": A_NAME})
    app_client.put(
        "/api/v1/me/consents",
        headers=_h(a),
        json={"scopes": {"checkins": True, "raw_csi": True}, "policy_version": "v1"},
    )
    session = ingest_session(db, a["user_id"], _night(tmp_path / "src_a"))
    db.add(SafetyEvent(user_id=a["user_id"], source="test", reason="r", details_enc={"k": 1}))
    flag = Flag(
        user_id=a["user_id"],
        date=datetime(2026, 11, 1, tzinfo=UTC).date(),
        domain_pair="sleep_mood",
        phys_level=1,
        mental_level=1,
        state="watch",
        priority=0.5,
        components={},
        message_key="test",
    )
    db.add(flag)
    night = NightFeaturesRow(
        user_id=a["user_id"],
        date=datetime(2026, 11, 1, tzinfo=UTC).date(),
        presence_hours=7.0,
        rr_med=14.0,
        valid=True,
        session_ids=[session.id],
        source_kind="synthetic",
    )
    db.add(night)
    db.add(
        CheckinDaily(
            user_id=a["user_id"],
            date=datetime(2026, 11, 1, tzinfo=UTC).date(),
            slot="am",
            instrument_id="daily_am",
            instrument_version="1.0",
            answers={"sleep_quality": 1, "energy": 1, "mood": 1},
        )
    )
    db.add(Baseline(user_id=a["user_id"], feature="rr_med", n=5, window_days=28))
    db.commit()
    surveys.load_catalog(db)
    job = jobs.submit_job(db, a["user_id"], "run_nightly", {"date": "2026-11-01"})
    inbox_a = sessions_svc.inbox_root(a["user_id"]) / "night_a"
    shutil.copytree(tmp_path / "src_a", inbox_a)
    resp = app_client.post(
        "/api/v1/responses",
        headers=_h(a),
        json={
            "instrument_id": "phq2",
            "instrument_version": "1.0",
            "answers": {"phq2_1": 2, "phq2_2": 3},
        },
    )
    assert resp.status_code == 200 and resp.json()["stored"], resp.text
    # A finished Monitor session stored under A, with the same id the {session_id} routes use,
    # so B addressing it proves the monitor routes are user-scoped (not just "id not found").
    from backend.services import monitor as monitor_svc

    mon_dir = monitor_svc.runs_root(a["user_id"]) / session.id
    mon_dir.mkdir(parents=True)
    (mon_dir / "summary.json").write_text(
        f'{{"id": "{session.id}", "mode": "heart_rate", '
        '"created_at": "2026-11-01T23:00:00+00:00"}'
    )
    return {
        "a": a,
        "b": b,
        "sample_id": "theta0_alt_position_manual_1min",  # a real saved capture (demo-only)
        "a_user_id": a["user_id"],
        "a_session_id": session.id,
        "session_id": session.id,  # OpenAPI template names, for id-addressed routes
        "job_id": job.id,
        "a_flag_id": flag.id,
        "day": "2026-11-01",  # A's night date (/nights/{day})
        "a_response_id": resp.json()["id"],
        "instrument_id": "phq2",
        # Strings that must never appear in anything B receives.
        "a_markers": [
            a["user_id"],
            "alice@example.com",
            A_NAME,
            session.id,
            job.id,
            flag.id,
            night.id,
            resp.json()["id"],
            a["access_token"],
            a["refresh_token"],
        ],
    }


@pytest.fixture(params=ISOLATION_CASES, ids=lambda c: c.id)
def case(request) -> IsolationCase:
    return request.param


def _fill(obj: Any, world: dict[str, Any]) -> Any:
    """Fill {placeholders} in string values of a JSON body from ``world``."""
    if isinstance(obj, str):
        return obj.format(**world)
    if isinstance(obj, dict):
        return {k: _fill(v, world) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fill(v, world) for v in obj]
    return obj


def _snapshot(db, user_id: str) -> dict[str, list[tuple]]:
    """Every row of every table with a user_id column, for one user."""
    db.expire_all()
    snap = {}
    for t in Base.metadata.sorted_tables:
        if "user_id" in t.c:
            rows = db.execute(select(t).where(t.c.user_id == user_id)).all()
            snap[t.name] = sorted(tuple(map(repr, r)) for r in rows)
    return snap


# --------------------------------------------------------------------------- tests


def test_b_cannot_read_or_change_a(case: IsolationCase, app_client, db, world) -> None:
    before = _snapshot(db, world["a_user_id"])
    assert sum(len(v) for v in before.values()) >= 8  # A really has data to leak

    res = app_client.request(
        case.method,
        case.path.format(**world),
        headers=_h(world["b"]),
        json=_fill(case.json, world),
        params={k: str(v).format(**world) for k, v in case.params.items()},
    )

    assert res.status_code == case.expect, res.text
    for marker in world["a_markers"]:
        assert marker not in res.text, f"{case.id} leaked A's data"
    assert _snapshot(db, world["a_user_id"]) == before, f"{case.id} changed A's rows"
    me = app_client.get("/api/v1/me", headers=_h(world["a"]))  # A still works as before
    assert me.status_code == 200 and me.json()["display_name"] == A_NAME


def _user_owned_models() -> list[type]:
    return sorted(
        (m.class_ for m in Base.registry.mappers if issubclass(m.class_, UserOwned)),
        key=lambda c: c.__tablename__,
    )


def test_scoped_isolates_every_user_owned_table(db, world) -> None:
    """ACC-7: for every UserOwned model, scoped() for B returns none of A's rows and
    scoped() for A returns exactly A's rows."""
    a_id, b_id = world["a_user_id"], world["b"]["user_id"]
    models = _user_owned_models()
    assert len(models) >= 15  # every user-owned table in backend.models, not a hand-picked few
    tables_with_a_rows = []
    for m in models:
        a_rows = db.scalars(scoped(select(m), m, a_id)).all()
        b_rows = db.scalars(scoped(select(m), m, b_id)).all()
        assert all(r.user_id == a_id for r in a_rows), m.__tablename__
        assert all(r.user_id == b_id for r in b_rows), m.__tablename__
        raw_a = db.execute(select(m.__table__).where(m.__table__.c.user_id == a_id)).all()
        assert len(a_rows) == len(raw_a), m.__tablename__
        if a_rows:
            tables_with_a_rows.append(m.__tablename__)
    # The check is only meaningful where A has data: make sure the seed reaches these.
    assert {
        "consents",
        "profiles",
        "raw_files",
        "refresh_tokens",
        "safety_events",
        "sessions",
        "survey_responses",
        "flags",
        "night_features",
        "checkins_daily",
        "baselines",
    } <= set(tables_with_a_rows), tables_with_a_rows


def test_export_service_is_scoped(db, world) -> None:
    out = repr(acc.export_user(db, world["b"]["user_id"]))
    for marker in world["a_markers"]:
        assert marker not in out


def test_every_route_has_a_case(app_client) -> None:
    routes = {
        (method, path) for path, ops in app_client.app.openapi()["paths"].items() for method in ops
    }
    covered = {(c.method, c.path) for c in ISOLATION_CASES}
    missing = sorted(routes - covered - EXEMPT)
    assert not missing, f"add an IsolationCase (or EXEMPT entry) for: {missing}"
    assert not covered - routes, f"cases for routes that do not exist: {covered - routes}"

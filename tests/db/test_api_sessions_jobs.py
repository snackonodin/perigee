from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from backend import db as db_mod
from backend import worker
from backend.main import create_app
from backend.models import Base, PipelineRun, WindowEstimateRow
from backend.services import accounts, runs

PW = "long enough password"


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    Base.metadata.create_all(engine)
    app = create_app(with_lifespan=False)
    assert {"backend.api.v1.sessions", "backend.api.v1.jobs"} <= set(app.state.mounted)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _signup(email: str) -> tuple[str, dict[str, str]]:
    with db_mod.SessionLocal() as s:
        r = accounts.signup(s, email, PW)
    return r.user_id, {"Authorization": f"Bearer {r.access_token}"}


@pytest.fixture
def alice(client) -> tuple[str, dict[str, str]]:
    return _signup("alice@example.test")


@pytest.fixture
def bob(client) -> tuple[str, dict[str, str]]:
    return _signup("bob@example.test")


@pytest.fixture
def inbox(data_dir: Path, capture_dir: Path, alice) -> Path:
    root = data_dir / "inbox" / alice[0]
    root.mkdir(parents=True)
    shutil.copytree(capture_dir, root / "night1")
    return root


# The capture fixture starts 2026-11-10 22:55Z.
RANGE = {"from": "2026-11-01T00:00:00Z", "to": "2026-11-20T00:00:00Z"}


def _register(client, headers, name="night1"):
    return client.post("/api/v1/sessions", json={"src_dir": name}, headers=headers)


@pytest.mark.parametrize(
    "method, path",
    [
        ("post", "/api/v1/sessions"),
        ("get", "/api/v1/sessions"),
        ("get", "/api/v1/sessions/x"),
        ("get", "/api/v1/windows?session_id=x"),
        ("post", "/api/v1/jobs/process"),
        ("get", "/api/v1/jobs/x"),
    ],
)
def test_routes_require_auth(client, method, path) -> None:
    r = getattr(client, method)(path)
    assert r.status_code == 401 and r.json()["error"] == "unauthorized"


def test_register_is_idempotent(client, alice, inbox) -> None:
    _, h = alice
    r1 = _register(client, h)
    assert r1.status_code == 201, r1.text
    r2 = _register(client, h)
    assert r2.status_code == 200 and r2.json()["id"] == r1.json()["id"]
    body = r1.json()
    assert body["stats"]["timestamp_wraps"] == 1 and len(body["files"]) == 4
    assert all(not f["path"].startswith("/") for f in body["files"])


@pytest.mark.parametrize(
    "name",
    ["../db", "/etc", "night1/../../db", "..", ".", "a\\b", "night1/./x", "%2e%2e", "",
     "missing", "a" * 200],
)  # fmt: skip
def test_register_rejects_bad_src_dir(client, alice, inbox, name) -> None:
    r = _register(client, alice[1], name)
    assert r.status_code in (400, 422)
    if name:
        assert name not in r.text  # never echo the input


def test_register_rejects_symlink_escape(client, alice, inbox, tmp_path) -> None:
    outside = tmp_path / "outside"
    shutil.copytree(inbox / "night1", outside)
    os.symlink(outside, inbox / "link")
    r = _register(client, alice[1], "link")
    assert r.status_code == 400 and r.json()["error"] == "bad_src_dir"


def test_register_ingest_error_is_400(client, alice, inbox) -> None:
    (inbox / "empty").mkdir()
    r = _register(client, alice[1], "empty")
    assert r.status_code == 400 and r.json()["error"] == "ingest_failed"


def test_list_default_range_and_explicit_range(client, alice, inbox) -> None:
    _, h = alice
    sid = _register(client, h).json()["id"]
    # Default window is the last 30 days from now; the fixture night is in 2026-11.
    listed = client.get("/api/v1/sessions", params=RANGE, headers=h).json()
    assert [s["id"] for s in listed] == [sid]
    later = {"from": "2026-11-11T00:00:00Z", "to": "2026-11-20T00:00:00Z"}
    assert client.get("/api/v1/sessions", params=later, headers=h).json() == []
    bad = {"from": "2026-11-20T00:00:00Z", "to": "2026-11-01T00:00:00Z"}
    assert client.get("/api/v1/sessions", params=bad, headers=h).status_code == 400


def test_default_range_is_30_days(client, alice, inbox, data_dir, monkeypatch) -> None:
    from backend.services import sessions as svc

    _, h = alice
    _register(client, h)
    now = datetime(2026, 11, 20, tzinfo=UTC)
    real = svc.datetime

    class _Fixed(real):  # type: ignore[misc, valid-type]
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(svc, "datetime", _Fixed)
    assert len(client.get("/api/v1/sessions", headers=h).json()) == 1
    monkeypatch.setattr(svc, "DEFAULT_RANGE", timedelta(days=5))
    assert client.get("/api/v1/sessions", headers=h).json() == []


def test_user_a_cannot_read_user_b(client, alice, bob, inbox) -> None:
    a_id, ha = alice
    _, hb = bob
    sid = _register(client, ha).json()["id"]
    with db_mod.SessionLocal() as s:
        s.add(WindowEstimateRow(
            user_id=a_id, session_id=sid, t_start=datetime(2026, 11, 10, 23, tzinfo=UTC),
            t_end=datetime(2026, 11, 10, 23, 1, tzinfo=UTC), rr_a=15.0, quality=0.9,
        ))  # fmt: skip
        s.commit()
    assert len(client.get("/api/v1/windows", params={"session_id": sid}, headers=ha).json()) == 1

    assert client.get("/api/v1/sessions", params=RANGE, headers=hb).json() == []
    r = _register(client, hb)  # A's inbox folder name means nothing in B's inbox
    assert r.status_code == 400 and r.json()["error"] == "bad_src_dir"
    assert client.get(f"/api/v1/sessions/{sid}", headers=hb).status_code == 404
    r = client.get("/api/v1/windows", params={"session_id": sid}, headers=hb)
    assert r.status_code == 404
    r = client.post("/api/v1/jobs/process", headers=hb,
                    json={"kind": "process_session", "params": {"session_id": sid}})  # fmt: skip
    assert r.status_code == 404
    body = {"kind": "process_session", "params": {"session_id": sid}}
    job = client.post("/api/v1/jobs/process", headers=ha, json=body).json()
    assert client.get(f"/api/v1/jobs/{job['id']}", headers=hb).status_code == 404
    assert client.get(f"/api/v1/jobs/{job['id']}", headers=ha).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "reset_everything", "params": {}},
        {"kind": "process_session", "params": {}},
        {"kind": "process_session", "params": {"session_id": "x", "user_id": "someone"}},
        {"kind": "run_nightly", "params": {"date": "yesterday"}},
    ],
)
def test_job_validation(client, alice, body) -> None:
    r = client.post("/api/v1/jobs/process", json=body, headers=alice[1])
    assert r.status_code == 400 and r.json()["error"] == "bad_job"


def test_job_lifecycle_with_worker(client, alice, inbox, monkeypatch) -> None:
    a_id, h = alice
    sid = _register(client, h).json()["id"]
    seen: dict = {}

    def fake(db, run: PipelineRun) -> str:
        seen.update(run.parameters, owner=run.user_id)
        return "ok"

    monkeypatch.setitem(runs._HANDLERS, "process_session", fake)
    r = client.post("/api/v1/jobs/process", headers=h,
                    json={"kind": "process_session", "params": {"session_id": sid}})  # fmt: skip
    assert r.status_code == 202 and r.json()["status"] == "queued"
    jid = r.json()["id"]

    with db_mod.SessionLocal() as s:
        assert worker.run_pending(s) == 1
        assert worker.run_pending(s) == 0  # nothing left
    got = client.get(f"/api/v1/jobs/{jid}", headers=h).json()
    assert got["status"] == "succeeded" and got["started"] and got["finished"]
    assert "log" not in got and "parameters" not in got
    assert seen == {"session_id": sid, "user_id": a_id, "owner": a_id}


def test_nightly_job_user_comes_from_token(client, alice, monkeypatch) -> None:
    a_id, h = alice
    r = client.post("/api/v1/jobs/process", headers=h,
                    json={"kind": "run_nightly", "params": {"date": "2026-11-10"}})  # fmt: skip
    assert r.status_code == 202
    with db_mod.SessionLocal() as s:
        row = s.get(PipelineRun, r.json()["id"])
        assert row.user_id == a_id and row.parameters == {"user_id": a_id, "date": "2026-11-10"}


def test_worker_failure_and_crash_do_not_stop_the_pass(client, alice, monkeypatch) -> None:
    _, h = alice
    calls = []

    def boom(db, run):
        calls.append(run.id)
        raise RuntimeError("bad night")

    monkeypatch.setitem(runs._HANDLERS, "run_nightly", boom)
    ids = [
        client.post(
            "/api/v1/jobs/process", headers=h, json={"kind": "run_nightly", "params": {"date": d}}
        ).json()["id"]  # fmt: skip
        for d in ("2026-11-09", "2026-11-10")
    ]
    with db_mod.SessionLocal() as s:
        assert worker.run_pending(s) == 2
    assert calls == ids
    for jid in ids:
        assert client.get(f"/api/v1/jobs/{jid}", headers=h).json()["status"] == "failed"


def test_start_stop_worker_idempotent_and_recovers(client, alice, monkeypatch) -> None:
    _, h = alice
    body = {"kind": "run_nightly", "params": {"date": "2026-11-10"}}
    jid = client.post("/api/v1/jobs/process", headers=h, json=body).json()["id"]
    with db_mod.SessionLocal() as s:  # simulate a crash mid-run
        s.get(PipelineRun, jid).status = "running"
        s.commit()
    worker.stop_worker()  # safe before start
    try:
        assert worker.start_worker(interval_s=0.05) is True
        assert worker.start_worker(interval_s=0.05) is False
        assert worker.is_running()
    finally:
        worker.stop_worker()
        worker.stop_worker()
    assert not worker.is_running()
    got = client.get(f"/api/v1/jobs/{jid}", headers=h).json()
    assert got["status"] == "failed"

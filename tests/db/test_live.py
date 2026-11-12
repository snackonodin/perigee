"""LIVE-1: SSE /api/v1/live/vitals (live tail, resume, replay, isolation, cleanup)."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import Engine, update

from backend import db as db_mod
from backend.main import create_app
from backend.models import Base, HeartEstimateRow, User, WindowEstimateRow
from backend.services import accounts
from backend.services import live as svc
from backend.services.ingestion import ingest_session

PW = "long enough password"
T0 = datetime(2026, 11, 10, 23, 0, tzinfo=UTC)


# ----------------------------------------------------------------- fixtures


def _app():
    app = create_app(with_lifespan=False)
    assert "backend.api.v1.live" in app.state.mounted  # registered in main.ROUTER_MODULES
    return app


@pytest.fixture
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "POLL_S", 0.02)
    monkeypatch.setattr(svc, "HEARTBEAT_S", 0.05)


@pytest.fixture
def client(engine: Engine, fast) -> Iterator[TestClient]:
    Base.metadata.create_all(engine)
    with TestClient(_app(), raise_server_exceptions=False) as c:
        yield c


def _signup(email: str) -> tuple[str, dict[str, str]]:
    with db_mod.SessionLocal() as s:
        r = accounts.signup(s, email, PW)
    return r.user_id, {"Authorization": f"Bearer {r.access_token}"}


@pytest.fixture
def alice(client):
    return _signup("alice@example.test")


@pytest.fixture
def bob(client):
    return _signup("bob@example.test")


@pytest.fixture
def a_session(alice, capture_dir) -> str:
    with db_mod.SessionLocal() as s:
        return ingest_session(s, alice[0], capture_dir).id


def _add(user_id: str, session_id: str, i: int, *, heart: bool = False, motion_score=None) -> None:
    t = T0 + timedelta(seconds=30 * i)
    with db_mod.SessionLocal() as s:
        if heart:
            s.add(HeartEstimateRow(user_id=user_id, session_id=session_id, t_start=t,
                                   t_end=t + timedelta(seconds=60), hr_bpm=60.0 + i,
                                   quality=0.5))  # fmt: skip
        else:
            s.add(WindowEstimateRow(user_id=user_id, session_id=session_id, t_start=t,
                                    t_end=t + timedelta(seconds=60), rr_a=14.0 + i,
                                    rr_b=14.5 + i, quality=0.9, motion_flag=i % 3 == 0,
                                    presence=i != 4, motion_score=motion_score))  # fmt: skip
        s.commit()


def _parse(text: str) -> list[dict]:
    """SSE text -> [{event, id, data}] (comments -> {"event": "ping"})."""
    out = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        if block.startswith(":"):
            out.append({"event": "ping"})
            continue
        ev: dict = {}
        for line in block.splitlines():
            k, _, v = line.partition(": ")
            ev[k] = json.loads(v) if k == "data" else v
        out.append(ev)
    return out


def _get(client, headers, **params) -> tuple[int, list[dict], str]:
    hdrs = dict(headers)
    if "last_event_id" in params:
        hdrs["Last-Event-ID"] = params.pop("last_event_id")
    r = client.get("/api/v1/live/vitals", headers=hdrs, params=params)
    return r.status_code, (_parse(r.text) if r.status_code == 200 else []), r.text


# ----------------------------------------------------------------- HTTP


def test_requires_auth(client) -> None:
    r = client.get("/api/v1/live/vitals")
    assert r.status_code == 401


def test_live_resume_from_start_streams_rows_in_order(client, alice, a_session) -> None:
    uid, h = alice
    for i in range(3):
        _add(uid, a_session, i)
    _add(uid, a_session, 1, heart=True)
    code, events, _ = _get(client, h, max_s=0.1, last_event_id="0-0")
    assert code == 200
    kinds = [e["event"] for e in events if e["event"] != "ping"]
    assert kinds[0] == "hello" and kinds[-1] == "bye"
    data = [e for e in events if e["event"] in ("window", "heart")]
    assert [e["event"] for e in data] == ["window", "window", "heart", "window"]  # time order
    assert all(e["data"]["experimental"] is True for e in data if e["event"] == "heart")
    assert data[0]["data"]["motion"] is True and data[0]["data"]["presence"] is True
    ids = [tuple(map(int, e["id"].split("-"))) for e in data]
    assert ids == sorted(ids)  # cursor never goes backwards
    assert events[-1]["data"] == {"reason": "max_s"} and events[-1]["id"] == data[-1]["id"]


def test_live_default_starts_now_and_tails_new_rows(client, alice, a_session) -> None:
    uid, h = alice
    _add(uid, a_session, 0)  # before connecting: not sent in live mode

    def writer() -> None:
        time.sleep(0.15)
        _add(uid, a_session, 7)
        _add(uid, a_session, 7, heart=True)

    t = threading.Thread(target=writer)
    t.start()
    code, events, _ = _get(client, h, max_s=0.6)
    t.join()
    data = [e for e in events if e["event"] in ("window", "heart")]
    assert code == 200 and [e["event"] for e in data] == ["window", "heart"]
    assert data[0]["data"]["rr_a"] == 21.0  # row 7, not row 0


def test_resume_with_last_event_id_skips_seen_rows(client, alice, a_session) -> None:
    uid, h = alice
    for i in range(4):
        _add(uid, a_session, i)
    _, first, _ = _get(client, h, max_s=0.05, last_event_id="0-0")
    mid = [e for e in first if e["event"] == "window"][1]["id"]
    _, again, _ = _get(client, h, max_s=0.05, last_event_id=mid)
    assert [e["data"]["rr_a"] for e in again if e["event"] == "window"] == [16.0, 17.0]
    _, bad, _ = _get(client, h, max_s=0.05, last_event_id="garbage")  # ignored: live from now
    assert not [e for e in bad if e["event"] == "window"]


def test_b_never_receives_a_events(client, alice, bob, a_session) -> None:
    uid, ha = alice
    _, hb = bob
    for i in range(3):
        _add(uid, a_session, i)
        _add(uid, a_session, i, heart=True)
    code, events, text = _get(client, hb, max_s=0.05, last_event_id="0-0")
    assert code == 200
    assert [e["event"] for e in events if e["event"] != "ping"] == ["hello", "bye"]
    assert a_session not in text and uid not in text
    code, _, text = _get(client, hb, replay_session=a_session, speed=10_000)
    assert code == 404 and a_session not in text
    # A sees their own
    _, a_events, _ = _get(client, ha, max_s=0.05, last_event_id="0-0")
    assert len([e for e in a_events if e["event"] in ("window", "heart")]) == 6


def test_replay_is_deterministic_and_complete(client, alice, a_session) -> None:
    uid, h = alice
    for i in (2, 0, 1):  # inserted out of time order
        _add(uid, a_session, i)
    _add(uid, a_session, 1, heart=True)
    runs = [_get(client, h, replay_session=a_session, speed=10_000)[1] for _ in range(2)]
    assert runs[0] == runs[1]
    ev = [e for e in runs[0] if e["event"] != "ping"]
    assert ev[0]["event"] == "hello" and ev[0]["data"]["events"] == 4
    body = ev[1:-1]
    assert [e["event"] for e in body] == ["window", "window", "heart", "window"]
    assert [e["data"]["seq"] for e in body] == [0, 1, 2, 3]
    assert all(e["data"]["replay"] is True for e in body)
    assert [e["data"]["t_start"] for e in body] == sorted(e["data"]["t_start"] for e in body)
    assert ev[-1] == {"event": "end", "data": {"events": 4}}


def test_replay_unknown_or_bad_params(client, alice) -> None:
    _, h = alice
    assert _get(client, h, replay_session="nope")[0] == 404
    assert _get(client, h, replay_session="x", speed=0)[0] == 422
    assert _get(client, h, max_s=10_000)[0] == 422


# ----------------------------------------------------------------- generator level


async def _never() -> bool:
    return False


async def _collect(agen, limit: int = 1000) -> list[str]:
    out = []
    async for chunk in agen:
        out.append(chunk)
        if len(out) >= limit:
            break
    return out


def test_heartbeat_when_idle(engine, fast) -> None:
    Base.metadata.create_all(engine)
    uid, _ = _signup("idle@example.test")
    t = {"now": 0.0}

    async def fake_sleep(s: float) -> None:
        t["now"] += s

    chunks = asyncio.run(_collect(svc.live_stream(
        uid, _never, max_s=1.0, poll_s=0.1, heartbeat_s=0.3, sleep=fake_sleep,
        clock=lambda: t["now"],
    )))  # fmt: skip
    assert chunks.count(svc.HEARTBEAT) == 3  # at ~0.3, 0.6, 0.9 s of a 1 s stream
    assert chunks[0].startswith("id: 0-0\nevent: hello") and "event: bye" in chunks[-1]
    assert svc.active_streams(uid) == 0


def test_replay_waits_scale_with_speed_and_are_capped(client, alice, a_session) -> None:
    uid, _ = alice
    _add(uid, a_session, 0)
    _add(uid, a_session, 1)  # +30 s
    _add(uid, a_session, 40)  # +1170 s later: capped
    waits: list[float] = []

    async def fake_sleep(s: float) -> None:
        waits.append(s)

    asyncio.run(_collect(svc.replay_stream(uid, a_session, _never, speed=10.0,
                                           heartbeat_s=100.0, sleep=fake_sleep)))  # fmt: skip
    assert waits == [pytest.approx(3.0), pytest.approx(svc.MAX_GAP_S)]


def test_disconnect_and_close_clean_up(client, alice, a_session) -> None:
    uid, _ = alice
    polls = {"n": 0}

    async def gone_after_two() -> bool:
        polls["n"] += 1
        return polls["n"] > 2

    async def run() -> list[str]:
        return await _collect(svc.live_stream(uid, gone_after_two, max_s=60.0, poll_s=0.0))

    asyncio.run(run())
    assert polls["n"] == 3 and svc.active_streams(uid) == 0

    async def close_mid_stream() -> None:  # what Starlette does when the client goes away
        agen = svc.live_stream(uid, _never, max_s=60.0, poll_s=0.01)
        await agen.__anext__()
        assert svc.active_streams(uid) == 1
        await agen.aclose()

    asyncio.run(close_mid_stream())
    assert svc.active_streams(uid) == 0


def test_disabled_user_stream_ends(client, alice) -> None:
    uid, _ = alice
    with db_mod.SessionLocal() as s:
        s.execute(update(User).where(User.id == uid).values(status="disabled"))
        s.commit()
    chunks = asyncio.run(_collect(svc.live_stream(uid, _never, max_s=60.0, poll_s=0.0)))
    assert '"reason":"unauthorized"' in chunks[-1] and svc.active_streams(uid) == 0


# ----------------------------------------------------------------- real server disconnect


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_real_client_disconnect_cleans_up(client, alice, a_session) -> None:
    uid, h = alice
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(_app(), host="127.0.0.1", port=port,
                                           log_level="warning", lifespan="off"))  # fmt: skip
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started
        url = f"http://127.0.0.1:{port}/api/v1/live/vitals"
        with httpx.Client(timeout=5) as hc, hc.stream("GET", url, headers=h) as r:
            assert r.status_code == 200
            assert next(r.iter_lines()).startswith("id: ")  # hello arrived
            assert svc.active_streams(uid) == 1
        deadline = time.monotonic() + 5  # client closed: server must notice and clean up
        while svc.active_streams(uid) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert svc.active_streams(uid) == 0
    finally:
        server.should_exit = True
        th.join(timeout=10)


def test_motion_score_streamed_when_present(client, alice, a_session) -> None:
    uid, h = alice
    _add(uid, a_session, 0, motion_score=0.73)
    _add(uid, a_session, 1)  # not computed yet
    _, events, _ = _get(client, h, max_s=0.05, last_event_id="0-0")
    scores = [e["data"]["motion_score"] for e in events if e["event"] == "window"]
    assert scores == [0.73, None]
    _, replay, _ = _get(client, h, replay_session=a_session, speed=10_000)
    assert [e["data"]["motion_score"] for e in replay if e["event"] == "window"] == [0.73, None]

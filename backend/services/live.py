"""Live vitals for the SSE endpoint: tail a user's new estimates, or replay a session.

Live mode polls window_estimates and heart_estimates for ONE user (every query goes
through scoped()) and yields rows newer than a cursor. The cursor is the pair of SQLite
rowids (windows, hearts); it is sent as the SSE event id, so a reconnecting EventSource
(Last-Event-ID) resumes exactly where it stopped. Polling the DB (not an in-process bus)
means rows written by any process (API, CLI, injection) are seen.

Replay mode yields one stored session's windows and heart estimates in time order,
spaced by their real time gaps divided by `speed` (each gap capped at MAX_GAP_S).
The event sequence is deterministic for a given session.

Heart estimates are always flagged experimental (FR8).
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import literal_column, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend import db as db_mod
from backend.models import CaptureSession, HeartEstimateRow, User, WindowEstimateRow, scoped

POLL_S = 1.0  # how often live mode checks for new rows
HEARTBEAT_S = 15.0  # SSE comment ping so proxies and clients keep the connection
MAX_STREAM_S = 300.0  # a live stream ends after this; EventSource reconnects and resumes
MAX_GAP_S = 5.0  # replay: longest wait between two events, after dividing by speed
BATCH = 500  # max rows per table per poll

# --------------------------------------------------------------------- stream registry
# Counts open streams per user, so tests (and ops) can check that disconnects clean up.
_lock = threading.Lock()
_active: dict[str, int] = {}


def active_streams(user_id: str | None = None) -> int:
    with _lock:
        return _active.get(user_id, 0) if user_id else sum(_active.values())


def _enter(user_id: str) -> None:
    with _lock:
        _active[user_id] = _active.get(user_id, 0) + 1


def _leave(user_id: str) -> None:
    with _lock:
        n = _active.get(user_id, 0) - 1
        if n > 0:
            _active[user_id] = n
        else:
            _active.pop(user_id, None)


# --------------------------------------------------------------------- events


@dataclass(frozen=True)
class Cursor:
    window: int = 0
    heart: int = 0

    def as_id(self) -> str:
        return f"{self.window}-{self.heart}"

    @classmethod
    def parse(cls, raw: str | None) -> Cursor | None:
        """Parse a Last-Event-ID ("<window rowid>-<heart rowid>"); None if absent/invalid."""
        if not raw:
            return None
        parts = raw.strip().split("-")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            return None
        return cls(int(parts[0]), int(parts[1]))


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z") if dt else None


def window_payload(w: WindowEstimateRow) -> dict[str, Any]:
    return {
        "session_id": w.session_id,
        "t_start": _iso(w.t_start),
        "t_end": _iso(w.t_end),
        "rr_a": w.rr_a,
        "rr_b": w.rr_b,
        "pnr_db": w.pnr_db,
        "quality": w.quality,
        "motion": w.motion_flag,
        "motion_score": w.motion_score,  # None until the motion estimator fills it
        "presence": w.presence,
    }


def heart_payload(h: HeartEstimateRow) -> dict[str, Any]:
    return {
        "session_id": h.session_id,
        "t_start": _iso(h.t_start),
        "t_end": _iso(h.t_end),
        "hr_bpm": h.hr_bpm,
        "quality": h.quality,
        "experimental": True,  # FR8: never presented as validated
    }


def sse(event: str, data: dict[str, Any], event_id: str | None = None) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append("data: " + json.dumps(data, sort_keys=True, separators=(",", ":")))
    return "\n".join(lines) + "\n\n"


HEARTBEAT = ": ping\n\n"

# --------------------------------------------------------------------- DB access (sync)

_W_ROWID = literal_column("window_estimates.rowid")
_H_ROWID = literal_column("heart_estimates.rowid")


def is_active(db: Session, user_id: str) -> bool:
    return db.scalar(select(User.id).where(User.id == user_id, User.status == "active")) is not None


def current_cursor(db: Session, user_id: str) -> Cursor:
    """The newest rowids for this user: a live stream starts after them."""
    w = db.scalar(scoped(select(_W_ROWID), WindowEstimateRow, user_id).order_by(_W_ROWID.desc()))
    h = db.scalar(scoped(select(_H_ROWID), HeartEstimateRow, user_id).order_by(_H_ROWID.desc()))
    return Cursor(int(w or 0), int(h or 0))


def poll(db: Session, user_id: str, cur: Cursor) -> tuple[list[tuple[str, dict, str]], Cursor]:
    """New rows for user_id after cur, as (event, payload, id) in insertion order."""
    windows = db.execute(
        scoped(select(WindowEstimateRow, _W_ROWID), WindowEstimateRow, user_id)
        .where(_W_ROWID > cur.window)
        .order_by(_W_ROWID)
        .limit(BATCH)
    ).all()
    hearts = db.execute(
        scoped(select(HeartEstimateRow, _H_ROWID), HeartEstimateRow, user_id)
        .where(_H_ROWID > cur.heart)
        .order_by(_H_ROWID)
        .limit(BATCH)
    ).all()
    events: list[tuple[str, dict, str]] = []
    w_id, h_id = cur.window, cur.heart
    merged = [(row.t_start, 0, rid, "window", row) for row, rid in windows] + [
        (row.t_start, 1, rid, "heart", row) for row, rid in hearts
    ]
    for _, _, rid, kind, row in sorted(merged, key=lambda m: (m[0], m[1], m[2])):
        if kind == "window":
            w_id = max(w_id, int(rid))
            events.append(("window", window_payload(row), Cursor(w_id, h_id).as_id()))
        else:
            h_id = max(h_id, int(rid))
            events.append(("heart", heart_payload(row), Cursor(w_id, h_id).as_id()))
    return events, Cursor(w_id, h_id)


def owns_session(db: Session, user_id: str, session_id: str) -> bool:
    return (
        db.scalar(
            scoped(select(CaptureSession.id), CaptureSession, user_id).where(
                CaptureSession.id == session_id
            )
        )
        is not None
    )


def replay_events(db: Session, user_id: str, session_id: str) -> list[tuple[datetime, str, dict]]:
    """All of one session's estimates in deterministic time order: (t_start, event, payload)."""
    ws = db.scalars(
        scoped(select(WindowEstimateRow), WindowEstimateRow, user_id)
        .where(WindowEstimateRow.session_id == session_id)
        .order_by(WindowEstimateRow.t_start, WindowEstimateRow.id)
    ).all()
    hs = db.scalars(
        scoped(select(HeartEstimateRow), HeartEstimateRow, user_id)
        .where(HeartEstimateRow.session_id == session_id)
        .order_by(HeartEstimateRow.t_start, HeartEstimateRow.id)
    ).all()
    out = [(w.t_start, 0, w.id, "window", window_payload(w)) for w in ws] + [
        (h.t_start, 1, h.id, "heart", heart_payload(h)) for h in hs
    ]
    out.sort(key=lambda e: (e[0], e[1], e[2]))
    return [(t, kind, payload) for t, _, _, kind, payload in out]


def _with_db(fn: Callable[..., Any], *args: Any) -> Any:
    """Run fn(db, *args) in a short-lived session: no connection is held between polls."""
    with db_mod.SessionLocal() as db:
        return fn(db, *args)


# --------------------------------------------------------------------- streams (async)

Sleep = Callable[[float], Awaitable[None]]
Disconnected = Callable[[], Awaitable[bool]]


async def live_stream(
    user_id: str,
    is_disconnected: Disconnected,
    *,
    resume: Cursor | None = None,
    max_s: float | None = None,
    poll_s: float | None = None,
    heartbeat_s: float | None = None,
    sleep: Sleep = asyncio.sleep,
    clock: Callable[[], float] | None = None,
) -> AsyncIterator[str]:
    # Defaults resolve at call time, so the module constants can be tuned (and tests can).
    max_s = MAX_STREAM_S if max_s is None else min(max_s, MAX_STREAM_S)
    poll_s = POLL_S if poll_s is None else poll_s
    heartbeat_s = HEARTBEAT_S if heartbeat_s is None else heartbeat_s
    loop_clock = clock or asyncio.get_running_loop().time
    _enter(user_id)
    try:
        cur = resume or await run_in_threadpool(_with_db, current_cursor, user_id)
        yield sse(
            "hello",
            {"mode": "live", "poll_s": poll_s, "heartbeat_s": heartbeat_s, "max_s": max_s},
            cur.as_id(),
        )
        start = last_beat = loop_clock()
        while True:
            if await is_disconnected():
                return
            if not await run_in_threadpool(_with_db, is_active, user_id):
                yield sse("bye", {"reason": "unauthorized"})
                return
            events, cur = await run_in_threadpool(_with_db, poll, user_id, cur)
            for event, payload, event_id in events:
                yield sse(event, payload, event_id)
            now = loop_clock()
            if events:
                last_beat = now
            elif now - last_beat >= heartbeat_s:
                yield HEARTBEAT
                last_beat = now
            if now - start >= max_s:
                yield sse("bye", {"reason": "max_s"}, cur.as_id())
                return
            await sleep(poll_s)
    finally:
        _leave(user_id)


async def replay_stream(
    user_id: str,
    session_id: str,
    is_disconnected: Disconnected,
    *,
    speed: float,
    heartbeat_s: float | None = None,
    sleep: Sleep = asyncio.sleep,
) -> AsyncIterator[str]:
    """Replay a stored session. The caller must have checked owns_session first."""
    heartbeat_s = HEARTBEAT_S if heartbeat_s is None else heartbeat_s
    _enter(user_id)
    try:
        events = await run_in_threadpool(_with_db, replay_events, user_id, session_id)
        yield sse(
            "hello",
            {"mode": "replay", "session_id": session_id, "speed": speed, "events": len(events)},
        )
        prev: datetime | None = None
        for seq, (t, event, payload) in enumerate(events):
            if prev is not None:
                wait = min(max((t - prev).total_seconds(), 0.0) / speed, MAX_GAP_S)
                while wait > 0:  # sleep in slices so heartbeats and disconnects are timely
                    step = min(wait, heartbeat_s)
                    await sleep(step)
                    wait -= step
                    if wait > 0:
                        yield HEARTBEAT
            prev = t
            if await is_disconnected():
                return
            yield sse(event, {**payload, "replay": True, "seq": seq}, str(seq))
        yield sse("end", {"events": len(events)})
    finally:
        _leave(user_id)

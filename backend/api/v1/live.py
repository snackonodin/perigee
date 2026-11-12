"""Server-Sent Events: GET /api/v1/live/vitals. Thin; see backend.services.live.

Live (default): new window estimates (breathing, motion, presence) and heart estimates
(experimental) for the caller, as they are written. The stream ends after max_s with
a "bye" event; EventSource reconnects with Last-Event-ID and resumes.
Replay (?replay_session=<id>&speed=N): one of the caller's sessions, in time order.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES, ApiError
from backend.services import live as svc

router = APIRouter(prefix="/api/v1", tags=["live"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # disable proxy buffering (nginx)
    "Connection": "keep-alive",
}


@router.get(
    "/live/vitals",
    responses={200: {"content": {"text/event-stream": {}}}, **ERROR_RESPONSES},
    response_class=StreamingResponse,
)
def vitals(
    request: Request,
    user_id: CurrentUser,
    db: DbSession,
    replay_session: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    speed: Annotated[float, Query(gt=0, le=10_000)] = 1.0,
    max_s: Annotated[float | None, Query(gt=0, le=svc.MAX_STREAM_S)] = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    if replay_session is not None:
        if not svc.owns_session(db, user_id, replay_session):
            raise ApiError(404, "not_found", "session not found")
        db.close()  # never hold a DB connection for the life of a stream
        gen = svc.replay_stream(user_id, replay_session, request.is_disconnected, speed=speed)
    else:
        db.close()
        gen = svc.live_stream(
            user_id, request.is_disconnected, resume=svc.Cursor.parse(last_event_id), max_s=max_s
        )
    return StreamingResponse(gen, media_type="text/event-stream", headers=_SSE_HEADERS)

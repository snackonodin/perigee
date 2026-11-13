"""On-demand Monitor sessions (INTEGRATION_PLAN.md §7). Thin: logic in services.monitor.

Starting a session opens the ESP receiver for that session only. Responses show flags by
default; numbers appear with ``show_rates=true`` or for the measure the person chose.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.deps import CurrentUser
from backend.errors import ERROR_RESPONSES, ApiError
from backend.services import monitor as svc

router = APIRouter(prefix="/api/v1/monitor", tags=["monitor"], responses=ERROR_RESPONSES)


class MonitorStart(BaseModel):
    mode: Literal["sleep_analysis", "heart_rate", "breathing_rate"]


class MonitorSessionOut(BaseModel):
    """State of one Monitor session. ``summary`` is the experimental session result once
    ``state`` is ``complete``; it is never a clinical or validated sleep measure."""

    id: str
    mode: Literal["sleep_analysis", "heart_rate", "breathing_rate"]
    state: Literal[
        "connecting", "link_check", "calibrating", "running", "finalizing",
        "complete", "link_error", "stopped",
    ]
    created_at: str
    remaining_s: float | None = None
    rows_per_s: float | None = None
    error: str | None = None
    summary: dict[str, Any] | None = None


class MonitorModeOut(BaseModel):
    """How long a session of this mode takes (config.yaml monitor, placeholders)."""

    mode: Literal["sleep_analysis", "heart_rate", "breathing_rate"]
    calibration_s: float
    duration_s: float
    total_s: float


@router.get("/modes", response_model=list[MonitorModeOut])
def list_modes(user_id: CurrentUser) -> list[dict[str, Any]]:
    return svc.modes()


def _not_found() -> ApiError:
    return ApiError(404, "not_found", "no such monitor session")


@router.post("/sessions", status_code=202, response_model=MonitorSessionOut)
def start_session(body: MonitorStart, user_id: CurrentUser) -> dict[str, Any]:
    try:
        run = svc.start(user_id, body.mode)
    except svc.MonitorBusy:
        raise ApiError(
            409, "busy", "The sensor is already in use. Try again when it finishes."
        ) from None
    except svc.MonitorUnavailable:
        raise ApiError(503, "no_receiver", "No sensor is set up on this device.") from None
    return svc.public_view({**run.status(), "summary": None})


@router.get("/sessions", response_model=list[MonitorSessionOut])
def list_sessions(user_id: CurrentUser, show_rates: bool = Query(False)) -> list[dict[str, Any]]:
    return [svc.public_view(item, show_rates) for item in svc.list_runs(user_id)]


@router.get("/sessions/{session_id}", response_model=MonitorSessionOut)
def get_session(
    session_id: str, user_id: CurrentUser, show_rates: bool = Query(False)
) -> dict[str, Any]:
    item = svc.get(user_id, session_id)
    if item is None:
        raise _not_found()
    return svc.public_view(item, show_rates)


@router.post("/sessions/{session_id}/stop", status_code=202, response_model=MonitorSessionOut)
def stop_session(session_id: str, user_id: CurrentUser) -> dict[str, Any]:
    if not svc.stop(user_id, session_id):
        raise _not_found()
    item = svc.get(user_id, session_id)
    if item is None:
        raise _not_found()
    return svc.public_view(item)

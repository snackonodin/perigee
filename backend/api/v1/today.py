"""GET /today. Thin: logic in backend.services.readouts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.api.v1.guidance import GuidanceCardOut
from backend.api.v1.nights import FlagOut, NightOut
from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES
from backend.services import readouts

router = APIRouter(prefix="/api/v1", tags=["today"], responses=ERROR_RESPONSES)


class TodayFlagOut(FlagOut):
    guidance: list[GuidanceCardOut]


class PendingCheckin(BaseModel):
    slot: str
    instrument_id: str
    instrument_version: str | None = None


class BaselineOut(BaseModel):
    feature: str
    maturity: str
    n: int
    median: float | None = None
    mad: float | None = None
    window_days: int
    updated_at: datetime


class SyncStatus(BaseModel):
    state: str


class TodayOut(BaseModel):
    safety_screen_required: bool = Field(
        default=False,
        description="Server-driven safety lock: show the safety screen before anything "
        "else until a later clean check-in clears it.",
    )
    missing_safety_item: str | None = None
    date: date
    latest_night: NightOut | None = None
    flags: list[TodayFlagOut]
    pending_checkins: list[PendingCheckin]
    checkins_consent: bool
    baselines: list[BaselineOut]
    context_engine: dict[str, Any] | None = None
    sync_status: SyncStatus


@router.get("/today", response_model=TodayOut)
def get_today(db: DbSession, user_id: CurrentUser) -> dict[str, Any]:
    """Latest night, top 3 flags from the last 7 days (each with guidance cards; viewing
    records guidance_shown), today's pending check-ins, baseline maturity per feature,
    and sync status. Dates are UTC."""
    return readouts.today(db, user_id)

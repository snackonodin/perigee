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


class CabinOut(BaseModel):
    date: date
    ppco2_mmhg: float | None = None
    temp_c: float | None = None
    rh_pct: float | None = None
    level: str = Field(description="usual | elevated | high | no_reading (config hazards:)")


class ContextTagOut(BaseModel):
    kind: str = Field(description="cabin_co2 | symptoms | immune")
    text: str


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
    cabin: CabinOut | None = Field(default=None, description="Latest cabin air reading")
    context_tags: list[ContextTagOut] = Field(
        default_factory=list,
        description="Up to 2 hazard tags explaining a Watch/Alert night; never hide the flag",
    )
    sync_status: SyncStatus


@router.get("/today", response_model=TodayOut)
def get_today(db: DbSession, user_id: CurrentUser) -> dict[str, Any]:
    """Latest night, top 3 flags from the last 7 days (each with guidance cards; viewing
    records guidance_shown), today's pending check-ins, baseline maturity per feature,
    and sync status. Dates are UTC."""
    return readouts.today(db, user_id)

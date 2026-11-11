"""Read routes: nights, flags, weekly indices, check-ins. Thin: logic in services.readouts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES, ApiError
from backend.services import readouts

router = APIRouter(prefix="/api/v1", tags=["readouts"], responses=ERROR_RESPONSES)

DateQ = Annotated[date | None, Query()]


# --------------------------------------------------------------------------- response models
# Typed for the generated frontend client. Shapes match services.readouts exactly.


class NightInputs(BaseModel):
    session_ids: list[str] = Field(default_factory=list)


class NightOut(BaseModel):
    """One night's features (FR7). Heart rate is never exposed (FR8)."""

    id: str
    date: date
    rr_med: float | None = None
    rr_var: float | None = None
    presence_hours: float
    restless_frac: float
    onset: datetime | None = None
    wake: datetime | None = None
    midsleep: datetime | None = None
    quality: float
    valid: bool
    source_kind: str
    inputs: NightInputs
    run_id: str | None = None


class FlagOut(BaseModel):
    id: str
    date: date
    domain_pair: str
    phys_level: int
    mental_level: int
    state: str
    priority: float
    message_key: str
    components: dict[str, Any] = Field(
        description="Why the flag was raised: values, baselines, z-scores, catalog bands"
    )
    run_id: str | None = None
    created_at: datetime


class IndexOut(BaseModel):
    value: float
    band: str | None = None
    band_alert: bool
    direction: int | None = Field(
        default=None, description="+1: higher is worse; -1: higher is better"
    )


class IndicesOut(BaseModel):
    week_start: date
    indices: dict[str, IndexOut]
    run_id: str | None = None


class CheckinOut(BaseModel):
    id: str
    date: date
    slot: str
    instrument_id: str
    instrument_version: str
    answers: dict[str, Any]
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


def _range(start: date | None, end: date | None) -> tuple[date, date]:
    try:
        return readouts.resolve_range(start, end)
    except readouts.InvalidRange as e:
        raise ApiError(400, "invalid_range", str(e)) from None


@router.get("/nights", response_model=list[NightOut])
def list_nights(
    db: DbSession,
    user_id: CurrentUser,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: DateQ = None,
) -> list[dict[str, Any]]:
    """Night features in [from, to] (inclusive; default the last 14 days), newest first."""
    start, end = _range(from_, to)
    return readouts.list_nights(db, user_id, start, end)


@router.get("/nights/{day}", response_model=list[NightOut])
def get_night(day: date, db: DbSession, user_id: CurrentUser) -> list[dict[str, Any]]:
    """All rows for one night (one per source_kind). 404 if there are none."""
    rows = readouts.nights_on(db, user_id, day)
    if not rows:
        raise ApiError(404, "not_found", "no night features for that date")
    return rows


@router.get("/flags", response_model=list[FlagOut])
def list_flags(db: DbSession, user_id: CurrentUser, since: DateQ = None) -> list[dict[str, Any]]:
    """Flags since a date (default the last 14 days), with components (the "why")."""
    start, _ = _range(since, None)
    return readouts.list_flags(db, user_id, start)


@router.get("/indices", response_model=IndicesOut)
def get_indices(db: DbSession, user_id: CurrentUser, week: DateQ = None) -> dict[str, Any]:
    """Weekly indices for the ISO week (Monday start) containing ``week`` (default this week)."""
    return readouts.indices_for_week(db, user_id, week)


@router.get("/checkins", response_model=list[CheckinOut])
def list_checkins(
    db: DbSession,
    user_id: CurrentUser,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: DateQ = None,
) -> list[dict[str, Any]]:
    """Daily check-ins in [from, to] (inclusive; default the last 14 days)."""
    start, end = _range(from_, to)
    return readouts.list_checkins(db, user_id, start, end)

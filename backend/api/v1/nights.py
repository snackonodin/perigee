"""Read routes: nights, flags, weekly indices, check-ins. Thin: logic in services.readouts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES, ApiError
from backend.services import readouts

router = APIRouter(prefix="/api/v1", tags=["readouts"], responses=ERROR_RESPONSES)

DateQ = Annotated[date | None, Query()]


def _range(start: date | None, end: date | None) -> tuple[date, date]:
    try:
        return readouts.resolve_range(start, end)
    except readouts.InvalidRange as e:
        raise ApiError(400, "invalid_range", str(e)) from None


@router.get("/nights")
def list_nights(
    db: DbSession,
    user_id: CurrentUser,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: DateQ = None,
) -> list[dict[str, Any]]:
    """Night features in [from, to] (inclusive; default the last 14 days), newest first."""
    start, end = _range(from_, to)
    return readouts.list_nights(db, user_id, start, end)


@router.get("/nights/{day}")
def get_night(day: date, db: DbSession, user_id: CurrentUser) -> list[dict[str, Any]]:
    """All rows for one night (one per source_kind). 404 if there are none."""
    rows = readouts.nights_on(db, user_id, day)
    if not rows:
        raise ApiError(404, "not_found", "no night features for that date")
    return rows


@router.get("/flags")
def list_flags(db: DbSession, user_id: CurrentUser, since: DateQ = None) -> list[dict[str, Any]]:
    """Flags since a date (default the last 14 days), with components (the "why")."""
    start, _ = _range(since, None)
    return readouts.list_flags(db, user_id, start)


@router.get("/indices")
def get_indices(db: DbSession, user_id: CurrentUser, week: DateQ = None) -> dict[str, Any]:
    """Weekly indices for the ISO week (Monday start) containing ``week`` (default this week)."""
    return readouts.indices_for_week(db, user_id, week)


@router.get("/checkins")
def list_checkins(
    db: DbSession,
    user_id: CurrentUser,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: DateQ = None,
) -> list[dict[str, Any]]:
    """Daily check-ins in [from, to] (inclusive; default the last 14 days)."""
    start, end = _range(from_, to)
    return readouts.list_checkins(db, user_id, start, end)

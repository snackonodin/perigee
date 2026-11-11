"""GET /today. Thin: logic in backend.services.readouts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES
from backend.services import readouts

router = APIRouter(prefix="/api/v1", tags=["today"], responses=ERROR_RESPONSES)


@router.get("/today")
def get_today(db: DbSession, user_id: CurrentUser) -> dict[str, Any]:
    """Latest night, top 3 flags from the last 7 days (each with guidance cards; viewing
    records guidance_shown), today's pending check-ins, baseline maturity per feature,
    and sync status. Dates are UTC."""
    return readouts.today(db, user_id)

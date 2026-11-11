"""Guidance cards for one of the user's flags. Thin: logic in backend.services.guidance."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES, ApiError
from backend.services import guidance

router = APIRouter(prefix="/api/v1", tags=["guidance"], responses=ERROR_RESPONSES)


class GuidanceCardOut(BaseModel):
    card_key: str
    title: str
    body: str
    contact_support_text: str
    source_note: str
    reviewed_by: str | None = None
    matched_signals: list[str]


@router.get("/guidance", response_model=list[GuidanceCardOut])
def get_guidance(
    db: DbSession, user_id: CurrentUser, flag_id: str = Query(min_length=1, max_length=36)
) -> list[dict]:
    """Up to 3 conservative cards for the flag; each view is recorded in guidance_shown.
    404 if the flag does not exist or belongs to someone else."""
    try:
        return guidance.select_guidance(db, user_id, flag_id)
    except guidance.UnknownFlag:
        raise ApiError(404, "not_found", "unknown flag") from None

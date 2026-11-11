"""Instrument catalog routes. Thin: logic lives in backend.services.surveys."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES, ApiError
from backend.services import surveys

router = APIRouter(prefix="/api/v1", tags=["surveys"], responses=ERROR_RESPONSES)


class InstrumentSummary(BaseModel):
    id: str
    name: str
    version: str
    timeframe: str | None = None
    license_note: str | None = None
    source_url: str | None = None
    items: int


@router.get("/instruments", response_model=list[InstrumentSummary])
def list_instruments(db: DbSession, user_id: CurrentUser) -> list[dict]:
    return surveys.list_instruments(db)


@router.get("/instruments/{instrument_id}")
def get_instrument(instrument_id: str, db: DbSession, user_id: CurrentUser) -> dict[str, Any]:
    """Full catalog definition: items, options, scoring, safety_trigger, sources."""
    try:
        return surveys.get_instrument(db, instrument_id)
    except surveys.UnknownInstrument:
        raise ApiError(404, "not_found", "unknown instrument") from None

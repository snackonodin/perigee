"""GET /persona. Thin: logic in backend.services.personality."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES
from backend.services import personality

router = APIRouter(prefix="/api/v1", tags=["persona"], responses=ERROR_RESPONSES)


class PersonaMatrixOut(BaseModel):
    stability_score: float
    agency_score: float
    quadrant_name: str


class PersonaOut(BaseModel):
    available: bool
    source: str | None = None
    updated_at: str | None = None
    traits: dict[str, float]
    persona_matrix: PersonaMatrixOut | None = None


@router.get("/persona", response_model=PersonaOut)
def get_persona(db: DbSession, user_id: CurrentUser) -> dict[str, Any]:
    """The caller's persona from the Mini-IPIP quiz (instrument mini_ipip), ready as soon
    as it is submitted; no nights needed. available=false until the quiz is taken.
    Traits (E, A, C, N, O; 4-20 each) shape wording only, never scores or alerts."""
    return personality.readout(db, user_id)

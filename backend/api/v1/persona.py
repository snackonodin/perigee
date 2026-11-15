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


class AdviceOut(BaseModel):
    tag: str
    text: str


class PartsProgressOut(BaseModel):
    done: list[str]
    total: int
    answers_kept: bool


class ProfileAxisOut(BaseModel):
    key: str
    label: str
    level: float  # 0-1 tendency, not a score


class TypeShareOut(BaseModel):
    type: str
    share: float  # 0-1, the four sum to 1; display only


class PersonaOut(BaseModel):
    available: bool
    source: str | None = None
    updated_at: str | None = None
    traits: dict[str, float]
    persona_matrix: PersonaMatrixOut | None = None
    style: dict[str, bool] = {}
    advice: list[AdviceOut] = []
    progress: PartsProgressOut | None = None
    profile: list[ProfileAxisOut] = []
    type_mix: list[TypeShareOut] = []


@router.get("/persona", response_model=PersonaOut)
def get_persona(db: DbSession, user_id: CurrentUser) -> dict[str, Any]:
    """The caller's persona, ready as soon as a persona quiz is submitted (no nights needed).
    psyche60 (preferred): quadrant + feedback-style flags + advice matched to the latest
    night and recent check-ins (empty while a safety screen is pending). mini_ipip: traits.
    available=false until a quiz is taken. Never changes scores, alerts or the safety path."""
    return personality.readout(db, user_id)

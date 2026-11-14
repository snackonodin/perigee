"""GET /pet/bubble. Thin: logic in backend.services.pet_dialogue."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES
from backend.services import pet_dialogue

router = APIRouter(prefix="/api/v1", tags=["pet"], responses=ERROR_RESPONSES)


class PetBubbleOut(BaseModel):
    id: str
    voice: str
    badge: str
    playful: bool
    pet_animation: str
    bubble: str | None = None
    micro_try: str | None = None
    ui_action: str | None = None
    disclaimer: str | None = None


@router.get("/pet/bubble", response_model=PetBubbleOut)
def get_bubble(db: DbSession, user_id: CurrentUser) -> dict[str, Any]:
    """The pet's single speech bubble for the caller. Safety first: while a safety screen is
    pending it is the crisis card (playful=false, ui_action HALT_AND_OPEN_CRISIS_SCREEN). Voice
    comes from the persona quadrant (traits never change thresholds). bubble=null before the
    first night. Never contains scores."""
    return pet_dialogue.select_bubble(db, user_id)

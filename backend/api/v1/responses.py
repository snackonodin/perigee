"""Survey / check-in submission. Thin: logic lives in backend.services.surveys.

Every outcome carries ``safety``: a 200 with ok=false for invalid input, and a
500 with the same body shape if storage fails. The frontend must act on
safety.show=true whatever else happened.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES
from backend.schemas.contracts import SafetyResult
from backend.services import surveys

router = APIRouter(prefix="/api/v1", tags=["surveys"])


class ResponseIn(BaseModel):
    """Loose on purpose: strict checks happen in the service, after the safety step,
    so a malformed answer can never skip the safety screen."""

    model_config = ConfigDict(extra="ignore")

    instrument_id: str = Field(min_length=1, max_length=32)
    # Any: a wrong type must reach the service (and its safety step), not fail here.
    instrument_version: Any = Field(default=None, json_schema_extra={"type": "string"})
    administered_at: Any = Field(  # ISO-8601 with timezone; defaults to now (UTC)
        default=None, json_schema_extra={"type": "string", "format": "date-time"}
    )
    answers: dict[str, Any]

    def __repr__(self) -> str:  # answers are red-class
        return f"ResponseIn(instrument_id={self.instrument_id!r}, answers=<redacted>)"

    __str__ = __repr__


class ResponseOut(BaseModel):
    ok: bool
    safety: SafetyResult
    id: str | None = None
    stored: bool = False
    answers_retained: bool = Field(
        default=False,
        description="True only if the item answers were kept: encrypted survey answers "
        "(survey_answers consent) or the check-in row (checkins consent).",
    )
    total: float | None = None
    scores: dict[str, Any] | None = None
    error: str | None = None  # "invalid" | "unknown_instrument" | "storage"
    errors: list[str] = Field(default_factory=list)  # item keys / field names only


_STORAGE_FAILED = {"model": ResponseOut, "description": "Not stored; safety still included"}


@router.post(
    "/responses",
    response_model=ResponseOut,
    responses={**{k: v for k, v in ERROR_RESPONSES.items() if k != 500}, 500: _STORAGE_FAILED},
)
def post_response(body: ResponseIn, db: DbSession, user_id: CurrentUser) -> Any:
    try:
        return surveys.submit_payload(
            db,
            user_id,
            body.instrument_id,
            body.instrument_version,
            body.administered_at,
            body.answers,
        )
    except surveys.SubmissionError as e:  # storage failure: still return safety
        out = ResponseOut(ok=False, safety=e.safety, error=e.kind, errors=e.errors)
        return JSONResponse(out.model_dump(mode="json"), status_code=500)

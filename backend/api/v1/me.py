"""/api/v1/me: profile, consents, export, delete. Every route acts on the token's user only."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from backend.api.v1.auth import account_errors
from backend.deps import CurrentUser, DbSession
from backend.errors import ERROR_RESPONSES
from backend.services import accounts as svc

router = APIRouter(prefix="/api/v1", tags=["me"], responses=ERROR_RESPONSES)

Scope = Literal["checkins", "survey_answers", "raw_csi", "share_summaries"]
assert set(Scope.__args__) == set(svc.CONSENT_SCOPES)  # keep the two lists in step


class MeOut(BaseModel):
    id: str
    email: str
    created_at: datetime
    is_synthetic: bool
    display_name: str | None
    timezone: str | None = Field(default=None, description="Legacy; not used. See station time.")
    station_time_offset_min: int | None = Field(
        default=None,
        description="Optional station clock as minutes from UTC (atomic time). Null = UTC.",
    )


class ProfilePatch(BaseModel):
    """Only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, max_length=svc.DISPLAY_NAME_MAX)
    timezone: str | None = Field(default=None, max_length=64)  # legacy, kept for old clients
    station_time_offset_min: int | None = Field(default=None, ge=-720, le=840)


class ConsentOut(BaseModel):
    granted: bool
    ts: datetime | None
    policy_version: str | None


class ConsentsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scopes: dict[Scope, bool] = Field(min_length=1)
    policy_version: str = Field(min_length=1, max_length=32)


@router.get("/me")
def get_me(user_id: CurrentUser, db: DbSession) -> MeOut:
    with account_errors():
        return MeOut(**svc.get_me(db, user_id))


@router.patch("/me")
def patch_me(body: ProfilePatch, user_id: CurrentUser, db: DbSession) -> MeOut:
    with account_errors():
        return MeOut(**svc.update_profile(db, user_id, body.model_dump(exclude_unset=True)))


@router.get("/me/consents")
def get_consents(user_id: CurrentUser, db: DbSession) -> dict[Scope, ConsentOut]:
    with account_errors():
        return svc.get_consents(db, user_id)


@router.put("/me/consents")
def put_consents(body: ConsentsIn, user_id: CurrentUser, db: DbSession) -> dict[Scope, ConsentOut]:
    with account_errors():
        return svc.set_consents(db, user_id, dict(body.scopes), body.policy_version)


@router.post("/me/export")
def export_me(user_id: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Everything stored about the caller, as JSON."""
    with account_errors():
        return svc.export_user(db, user_id)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user_id: CurrentUser, db: DbSession) -> None:
    """Delete the account, all its rows and its raw files under DATA_DIR. Irreversible."""
    with account_errors():
        svc.delete_user(db, user_id)

"""Instruments, survey responses, check-ins, indices, safety events, guidance."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    Float,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import (
    Base,
    JSONText,
    UserOwned,
    UTCDateTime,
    enum_check,
    utcnow,
    uuid_pk,
)
from backend.schemas.contracts import CheckinSlot


class Instrument(Base):
    """Global catalogue (not user-owned). Loaded from seeds/ by the surveys branch."""

    __tablename__ = "instrument_catalog"
    __table_args__ = (UniqueConstraint("instrument_id", "version"),)

    id: Mapped[str] = uuid_pk()
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    timeframe: Mapped[str | None] = mapped_column(String(64))
    license_note: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONText, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class SurveyResponseRow(UserOwned, Base):
    """Red class. `answers` maps to column answers_enc and holds ciphertext bytes only.

    Encryption lives in the accounts branch (backend.security.encrypt / EncryptedJSON);
    this model never sees plaintext.
    """

    __tablename__ = "survey_responses"

    id: Mapped[str] = uuid_pk()
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_version: Mapped[str] = mapped_column(String(32), nullable=False)
    administered_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    answers: Mapped[bytes] = mapped_column("answers_enc", LargeBinary, nullable=False)
    total: Mapped[float | None] = mapped_column(Float)
    scores: Mapped[dict[str, Any] | None] = mapped_column(JSONText)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"SurveyResponseRow(id={self.id!r}, instrument_id={self.instrument_id!r})"


class CheckinDaily(UserOwned, Base):
    __tablename__ = "checkins_daily"
    __table_args__ = (
        enum_check("slot", CheckinSlot),
        UniqueConstraint("user_id", "date", "slot"),
    )

    id: Mapped[str] = uuid_pk()
    date: Mapped[date] = mapped_column(Date, nullable=False)
    slot: Mapped[str] = mapped_column(String(4), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_version: Mapped[str] = mapped_column(String(32), nullable=False)
    answers: Mapped[dict[str, Any]] = mapped_column(JSONText, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONText, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class IndexValue(UserOwned, Base):
    """Weekly mental indices (one row per user, week, index name)."""

    __tablename__ = "indices"
    __table_args__ = (UniqueConstraint("user_id", "week_start", "name"),)

    id: Mapped[str] = uuid_pk()
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class SafetyEvent(UserOwned, Base):
    """Red class, minimal. Any free-text detail goes in details_enc as ciphertext."""

    __tablename__ = "safety_events"

    id: Mapped[str] = uuid_pk()
    ts: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    details_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class GuidanceCard(Base):
    """Global (not user-owned). Seeded by the surveys branch."""

    __tablename__ = "guidance_cards"

    id: Mapped[str] = uuid_pk()
    card_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONText, default=list, nullable=False)
    source_note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))


class GuidanceShown(UserOwned, Base):
    __tablename__ = "guidance_shown"

    id: Mapped[str] = uuid_pk()
    card_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("guidance_cards.id", ondelete="CASCADE"), nullable=False
    )
    flag_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("flags.id", ondelete="SET NULL")
    )
    shown_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

"""Test-only mirror of the backend.models tables the surveys service uses.

Copied from feat/db-ingest dec9546 (backend/models/base.py and mental.py).
Delete this file once that branch is merged; test_surveys_db.py then imports
the real models. Contains no tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy import (
    Float,
    ForeignKey,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.types import TypeDecorator

from backend.schemas.contracts import new_id

_TS_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    impl = String(27)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive datetime: timestamps must be timezone-aware")
        return value.astimezone(UTC).strftime(_TS_FORMAT)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return datetime.strptime(value, _TS_FORMAT).replace(tzinfo=UTC)


class JSONText(TypeDecorator[Any]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def process_result_value(self, value, dialect):
        return None if value is None else json.loads(value)


def uuid_pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=new_id)


class Base(DeclarativeBase):
    metadata = MetaData()


class UserOwned:
    @declared_attr
    def user_id(cls) -> Mapped[str]:  # noqa: N805
        return mapped_column(
            String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
        )


def scoped(stmt: Any, model: Any, user_id: str) -> Any:
    col = getattr(model, "user_id", None)
    if col is None:
        raise TypeError(f"{getattr(model, '__name__', model)!r} is not user-owned")
    if not user_id:
        raise ValueError("user_id is required")
    return stmt.where(col == user_id)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = uuid_pk()


class Instrument(Base):
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


class SafetyEvent(UserOwned, Base):
    __tablename__ = "safety_events"

    id: Mapped[str] = uuid_pk()
    ts: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    details_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


MODELS = SimpleNamespace(
    Base=Base,
    User=User,
    Instrument=Instrument,
    SurveyResponseRow=SurveyResponseRow,
    SafetyEvent=SafetyEvent,
    UserOwned=UserOwned,
    scoped=scoped,
)

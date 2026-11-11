"""Declarative base, column types and the UserOwned mixin.

Storage conventions (SQLite):
- Primary keys are UUID strings stored as TEXT.
- Timestamps are stored as fixed-width ISO-8601 UTC text ("...Z"), so they sort
  correctly as text. Naive datetimes are rejected.
- JSON is stored as TEXT (sorted keys, so equal values give equal text).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, Dialect, ForeignKey, MetaData, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.types import TypeDecorator

from backend.schemas.contracts import new_id

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

_TS_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware datetime <-> ISO-8601 UTC text."""

    impl = String(27)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive datetime: timestamps must be timezone-aware")
        return value.astimezone(UTC).strftime(_TS_FORMAT)

    def process_result_value(self, value: str | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return datetime.strptime(value, _TS_FORMAT).replace(tzinfo=UTC)


class JSONText(TypeDecorator[Any]):
    """JSON value stored as TEXT."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Any:
        return None if value is None else json.loads(value)


def uuid_pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=new_id)


def enum_check(column: str, enum: type[StrEnum], name: str | None = None) -> CheckConstraint:
    """CHECK (column IN (...)) built from a contracts enum, so the two never drift."""
    values = ", ".join(f"'{m.value}'" for m in enum)
    return CheckConstraint(f"{column} IN ({values})", name=name or column)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UserOwned:
    """Mixin: user_id FK to users.id, ON DELETE CASCADE, indexed, NOT NULL."""

    @declared_attr
    def user_id(cls) -> Mapped[str]:  # noqa: N805
        return mapped_column(
            String(36),
            ForeignKey("users.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )


def scoped(stmt: Any, model: Any, user_id: str) -> Any:
    """Restrict a select/update/delete to one user's rows.

    Raises TypeError for models without user_id, so a missing filter is loud.
    """
    col = getattr(model, "user_id", None)
    if col is None:
        raise TypeError(f"{getattr(model, '__name__', model)!r} is not user-owned")
    if not user_id:
        raise ValueError("user_id is required")
    return stmt.where(col == user_id)

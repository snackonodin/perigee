"""Window and night estimates, baselines, flags."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
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
from backend.schemas.contracts import Maturity, SourceKind


def _session_fk() -> Mapped[str]:
    return mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )


def _run_fk() -> Mapped[str | None]:
    return mapped_column(String(36), ForeignKey("pipeline_runs.id", ondelete="SET NULL"))


class WindowEstimateRow(UserOwned, Base):
    __tablename__ = "window_estimates"

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = _session_fk()
    t_start: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    t_end: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    rr_a: Mapped[float | None] = mapped_column(Float)
    rr_b: Mapped[float | None] = mapped_column(Float)
    pnr_db: Mapped[float | None] = mapped_column(Float)
    motion_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Continuous motion intensity from the motion estimator (f4); NULL when not computed.
    motion_score: Mapped[float | None] = mapped_column(Float)
    quality: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    presence: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    run_id: Mapped[str | None] = _run_fk()


class HeartEstimateRow(UserOwned, Base):
    """FR8: experimental only. The CHECK keeps a non-experimental row out of the DB."""

    __tablename__ = "heart_estimates"
    __table_args__ = (CheckConstraint("experimental = 1", name="experimental"),)

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = _session_fk()
    t_start: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    t_end: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    hr_bpm: Mapped[float | None] = mapped_column(Float)
    quality: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    experimental: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    run_id: Mapped[str | None] = _run_fk()


class NightFeaturesRow(UserOwned, Base):
    __tablename__ = "night_features"
    __table_args__ = (
        enum_check("source_kind", SourceKind),
        UniqueConstraint("user_id", "date", "source_kind"),
    )

    id: Mapped[str] = uuid_pk()
    date: Mapped[date] = mapped_column(Date, nullable=False)
    rr_med: Mapped[float | None] = mapped_column(Float)
    rr_var: Mapped[float | None] = mapped_column(Float)
    presence_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    restless_frac: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    onset: Mapped[datetime | None] = mapped_column(UTCDateTime)
    wake: Mapped[datetime | None] = mapped_column(UTCDateTime)
    midsleep: Mapped[datetime | None] = mapped_column(UTCDateTime)
    quality: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hr_med: Mapped[float | None] = mapped_column(Float)
    session_ids: Mapped[list[str]] = mapped_column(JSONText, default=list, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(16), default="csi", nullable=False)
    run_id: Mapped[str | None] = _run_fk()


class Baseline(UserOwned, Base):
    __tablename__ = "baselines"
    __table_args__ = (
        enum_check("maturity", Maturity),
        UniqueConstraint("user_id", "feature"),
    )

    id: Mapped[str] = uuid_pk()
    feature: Mapped[str] = mapped_column(String(64), nullable=False)
    median: Mapped[float | None] = mapped_column(Float)
    mad: Mapped[float | None] = mapped_column(Float)
    n: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    maturity: Mapped[str] = mapped_column(String(16), default="warm_up", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class Flag(UserOwned, Base):
    __tablename__ = "flags"

    id: Mapped[str] = uuid_pk()
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    domain_pair: Mapped[str] = mapped_column(String(64), nullable=False)
    phys_level: Mapped[int] = mapped_column(Integer, nullable=False)
    mental_level: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[float] = mapped_column(Float, nullable=False)
    components: Mapped[dict[str, Any]] = mapped_column(JSONText, default=dict, nullable=False)
    message_key: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str | None] = _run_fk()
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

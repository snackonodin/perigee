"""Recording sessions, raw files, markers, reference readings."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, UserOwned, UTCDateTime, enum_check, utcnow, uuid_pk
from backend.schemas.contracts import Posture, ReferenceKind, SourceKind


def _session_fk() -> Mapped[str]:
    return mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )


class CaptureSession(UserOwned, Base):
    """FR1 + FR4: one recording session and its capture stats (contracts.SessionRecord)."""

    __tablename__ = "sessions"
    __table_args__ = (
        enum_check("source_kind", SourceKind),
        enum_check("posture", Posture),
        UniqueConstraint("user_id", "raw_sha256"),
    )

    id: Mapped[str] = uuid_pk()
    start_utc: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    end_utc: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    condition: Mapped[str | None] = mapped_column(String(64))
    distance_m: Mapped[float | None] = mapped_column(Float)
    posture: Mapped[str | None] = mapped_column(String(16))
    paced_bpm: Mapped[float | None] = mapped_column(Float)
    reference_device: Mapped[str | None] = mapped_column(String(128))
    room_notes: Mapped[str | None] = mapped_column(Text)
    phone_model: Mapped[str | None] = mapped_column(String(128))
    source_kind: Mapped[str] = mapped_column(String(16), default="csi", nullable=False)
    raw_path: Mapped[str] = mapped_column(Text, nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    mean_rows_per_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_gap_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    gaps_over_50ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_changes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timestamp_wraps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pipeline_runs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class RawFile(UserOwned, Base):
    __tablename__ = "raw_files"
    __table_args__ = (UniqueConstraint("user_id", "sha256"),)

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = _session_fk()
    path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default="csi", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class Marker(UserOwned, Base):
    __tablename__ = "markers"

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = _session_fk()
    host_time: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)


class ReferenceReadingRow(UserOwned, Base):
    __tablename__ = "reference_readings"
    __table_args__ = (enum_check("kind", ReferenceKind),)

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = _session_fk()
    ts: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)

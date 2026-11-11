"""Pipeline runs (FR10 provenance)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, JSONText, UTCDateTime, enum_check, utcnow, uuid_pk
from backend.schemas.contracts import RunStatus


class PipelineRun(Base):
    """A run may belong to a user (jobs API, per-user processing) or be global (NULL).

    user_id is nullable so global runs fit; API reads always go through scoped().
    """

    __tablename__ = "pipeline_runs"
    __table_args__ = (enum_check("status", RunStatus),)

    id: Mapped[str] = uuid_pk()
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONText, default=dict, nullable=False)
    code_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hashes: Mapped[list[str]] = mapped_column(JSONText, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    started: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished: Mapped[datetime | None] = mapped_column(UTCDateTime)
    log: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

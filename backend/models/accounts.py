"""Users, tokens, profiles, consents, audit log."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DDL,
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, JSONText, UserOwned, UTCDateTime, utcnow, uuid_pk
from backend.security import EncryptedJSON


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:  # never show password_hash
        return f"User(id={self.id!r}, is_synthetic={self.is_synthetic!r})"


V_REAL_USERS_SQL = "CREATE VIEW v_real_users AS SELECT * FROM users WHERE is_synthetic = 0"
event.listen(User.__table__, "after_create", DDL(V_REAL_USERS_SQL))
event.listen(User.__table__, "before_drop", DDL("DROP VIEW IF EXISTS v_real_users"))


class RefreshToken(UserOwned, Base):
    """Only the sha256 of the token is stored, never the token itself."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = uuid_pk()
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Profile(UserOwned, Base):
    __tablename__ = "profiles"
    __table_args__ = (Index("uq_profiles_user_id", "user_id", unique=True),)

    id: Mapped[str] = uuid_pk()
    # Red class: Fernet ciphertext in display_name_enc (BLOB); plaintext str on the attribute.
    display_name: Mapped[str | None] = mapped_column("display_name_enc", EncryptedJSON)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONText, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class Consent(UserOwned, Base):
    """Current state per (user, scope). The change history lives in audit_log."""

    __tablename__ = "consents"
    __table_args__ = (UniqueConstraint("user_id", "scope"),)

    id: Mapped[str] = uuid_pk()
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)


class AuditLog(Base):
    """Who did what. Not user-owned: rows outlive the user (user_id -> NULL on delete).

    Never put passwords, tokens, survey answers, notes or medication names in details.
    """

    __tablename__ = "audit_log"

    id: Mapped[str] = uuid_pk()
    ts: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(128))
    details: Mapped[dict[str, Any]] = mapped_column(JSONText, default=dict, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

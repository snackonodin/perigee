"""Account lifecycle: signup, login, refresh, logout, profile, consents, export, delete.

Every query here filters by user_id. Errors are domain exceptions (AccountError
subclasses); routes map them to HTTP. Nothing sensitive is logged or audited.
"""

from __future__ import annotations

import base64
import logging
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend import security
from backend.config import get_settings

# TEMPORARY: repointed to backend.models at merge (see tests/api/_tmp_models.py).
from tests.api._tmp_models import AuditLog, Base, Consent, Profile, RefreshToken, User

log = logging.getLogger(__name__)

PASSWORD_MIN = 10
PASSWORD_MAX = 1024  # bounds hashing cost; not a policy value
CONSENT_SCOPES: tuple[str, ...] = ("checkins", "survey_answers", "raw_csi", "share_summaries")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Columns never exported, even to the account owner.
_EXPORT_EXCLUDE = {"password_hash", "token_hash"}


# --------------------------------------------------------------------------- errors


class AccountError(Exception):
    code = "account_error"


class InvalidInput(AccountError):
    code = "invalid_input"


class EmailTaken(AccountError):
    code = "email_taken"


class InvalidCredentials(AccountError):
    code = "invalid_credentials"


class InvalidRefreshToken(AccountError):
    code = "invalid_refresh_token"


class UserNotFound(AccountError):
    code = "not_found"


# --------------------------------------------------------------------------- helpers


@dataclass(frozen=True)
class AuthResult:
    user_id: str
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo; everything we store is UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def normalize_email(email: str) -> str:
    e = email.strip().lower()
    if len(e) > 320 or not _EMAIL_RE.match(e):
        raise InvalidInput("invalid email")
    return e


def _check_password(pw: str) -> None:
    if not PASSWORD_MIN <= len(pw) <= PASSWORD_MAX:
        raise InvalidInput(f"password must be {PASSWORD_MIN} to {PASSWORD_MAX} characters")


def audit(db: Session, user_id: str | None, action: str, **detail: Any) -> None:
    """Add an audit row (caller commits). Detail must hold no red-class values."""
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))


def _issue_tokens(db: Session, user_id: str) -> AuthResult:
    s = get_settings()
    plaintext, digest = security.new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=digest,
            expires_at=_now() + timedelta(days=s.refresh_token_days),
        )
    )
    return AuthResult(
        user_id=user_id,
        access_token=security.make_access_token(user_id),
        refresh_token=plaintext,
        expires_in=s.access_token_minutes * 60,
    )


def _revoke_all(db: Session, user_id: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def _active_user(db: Session, user_id: str) -> User:
    user = db.scalar(select(User).where(User.id == user_id, User.status == "active"))
    if user is None:
        raise UserNotFound("no such user")
    return user


def is_active_user(db: Session, user_id: str) -> bool:
    return db.scalar(select(User.id).where(User.id == user_id, User.status == "active")) is not None


# --------------------------------------------------------------------------- auth


def signup(db: Session, email: str, password: str) -> AuthResult:
    email = normalize_email(email)
    _check_password(password)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailTaken("email already registered")
    user = User(email=email, password_hash=security.hash_password(password))
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id))
    result = _issue_tokens(db, user.id)
    audit(db, user.id, "auth.signup")
    db.commit()
    log.info("signup user_id=%s", user.id)
    return result


def login(db: Session, email: str, password: str) -> AuthResult:
    try:
        email = normalize_email(email)
    except InvalidInput:
        security.burn_verify(password)
        raise InvalidCredentials("invalid email or password") from None
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        security.burn_verify(password)
        raise InvalidCredentials("invalid email or password")
    if not security.verify_password(user.password_hash, password) or user.status != "active":
        audit(db, user.id, "auth.login_failed")
        db.commit()
        raise InvalidCredentials("invalid email or password")
    result = _issue_tokens(db, user.id)
    audit(db, user.id, "auth.login")
    db.commit()
    log.info("login user_id=%s", user.id)
    return result


def refresh(db: Session, refresh_token: str) -> AuthResult:
    """Rotate: the presented token is revoked and a new pair issued.

    Presenting an already-revoked token is treated as theft: every token of that user is revoked.
    """
    row = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == security.hash_refresh_token(refresh_token)
        )
    )
    if row is None:
        raise InvalidRefreshToken("invalid refresh token")
    if row.revoked_at is not None:
        _revoke_all(db, row.user_id)
        audit(db, row.user_id, "auth.refresh_reuse")
        db.commit()
        log.warning("refresh token reuse user_id=%s; all tokens revoked", row.user_id)
        raise InvalidRefreshToken("invalid refresh token")
    if _aware(row.expires_at) <= _now() or not is_active_user(db, row.user_id):
        raise InvalidRefreshToken("invalid refresh token")
    row.revoked_at = _now()
    result = _issue_tokens(db, row.user_id)
    db.commit()
    return result


def logout(db: Session, refresh_token: str, user_id: str | None = None) -> None:
    """Revoke one refresh token. Unknown tokens are ignored (idempotent).

    With user_id, revoke only if the token belongs to that user.
    """
    stmt = update(RefreshToken).where(
        RefreshToken.token_hash == security.hash_refresh_token(refresh_token),
        RefreshToken.revoked_at.is_(None),
    )
    if user_id is not None:
        stmt = stmt.where(RefreshToken.user_id == user_id)
    db.execute(stmt.values(revoked_at=_now()))
    db.commit()


# --------------------------------------------------------------------------- profile


def get_me(db: Session, user_id: str) -> dict[str, Any]:
    user = _active_user(db, user_id)
    prof = db.scalar(select(Profile).where(Profile.user_id == user_id))
    return {
        "id": user.id,
        "email": user.email,
        "created_at": _aware(user.created_at),
        "is_synthetic": user.is_synthetic,
        "display_name": prof.display_name if prof else None,
        "timezone": prof.timezone if prof else None,
    }


def update_profile(db: Session, user_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Apply only the keys present in changes (display_name, timezone)."""
    _active_user(db, user_id)
    unknown = set(changes) - {"display_name", "timezone"}
    if unknown:
        raise InvalidInput(f"unknown profile fields: {sorted(unknown)}")
    tz = changes.get("timezone")
    if tz is not None:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise InvalidInput("unknown timezone") from None
    prof = db.scalar(select(Profile).where(Profile.user_id == user_id))
    if prof is None:
        prof = Profile(user_id=user_id)
        db.add(prof)
    for k, v in changes.items():
        setattr(prof, k, v)
    prof.updated_at = _now()
    db.commit()
    return get_me(db, user_id)


# --------------------------------------------------------------------------- consents


def get_consents(db: Session, user_id: str) -> dict[str, Any]:
    _active_user(db, user_id)
    rows = db.scalars(select(Consent).where(Consent.user_id == user_id)).all()
    by_scope = {r.scope: r for r in rows}
    return {
        scope: {
            "granted": by_scope[scope].granted if scope in by_scope else False,
            "ts": _aware(by_scope[scope].ts) if scope in by_scope else None,
            "policy_version": by_scope[scope].policy_version if scope in by_scope else None,
        }
        for scope in CONSENT_SCOPES
    }


def set_consents(
    db: Session, user_id: str, scopes: dict[str, bool], policy_version: str
) -> dict[str, Any]:
    """Set the given scopes. One audit row per scope whose value actually changed."""
    _active_user(db, user_id)
    unknown = set(scopes) - set(CONSENT_SCOPES)
    if unknown:
        raise InvalidInput(f"unknown consent scopes: {sorted(unknown)}")
    if not policy_version.strip():
        raise InvalidInput("policy_version is required")
    existing = {
        r.scope: r for r in db.scalars(select(Consent).where(Consent.user_id == user_id)).all()
    }
    now = _now()
    for scope, granted in scopes.items():
        row = existing.get(scope)
        before = row.granted if row else False
        if row is None:
            row = Consent(user_id=user_id, scope=scope)
            db.add(row)
        row.granted, row.ts, row.policy_version = granted, now, policy_version
        if before != granted:
            audit(db, user_id, "consent.change", scope=scope, granted=granted,
                  policy_version=policy_version)
    db.commit()
    return get_consents(db, user_id)


# --------------------------------------------------------------------------- export / delete


def _user_tables() -> list:
    """Every table with a user_id column, parents before children."""
    return [t for t in Base.metadata.sorted_tables if "user_id" in t.c]


def _jsonable(v: Any) -> Any:
    if isinstance(v, datetime):
        return _aware(v).isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bytes):
        return base64.b64encode(v).decode()
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_jsonable(x) for x in v]
    return v


def _rows(db: Session, table, where) -> list[dict[str, Any]]:
    cols = [c for c in table.c if c.name not in _EXPORT_EXCLUDE]
    return [
        {k: _jsonable(v) for k, v in r._mapping.items()}
        for r in db.execute(select(*cols).where(where))
    ]


def export_user(db: Session, user_id: str) -> dict[str, Any]:
    """All of the user's rows, as JSON-safe data. Encrypted fields come back decrypted."""
    _active_user(db, user_id)
    audit(db, user_id, "account.export")
    db.commit()
    users = Base.metadata.tables["users"]
    return {
        "exported_at": _now().isoformat(),
        "user": _rows(db, users, users.c.id == user_id)[0],
        "tables": {t.name: _rows(db, t, t.c.user_id == user_id) for t in _user_tables()},
    }


def _raw_dirs(db: Session, user_id: str, data_dir: Path) -> list[Path]:
    sessions = Base.metadata.tables.get("sessions")
    if sessions is None:
        return []
    raw_root = (data_dir / "raw").resolve()
    dirs = []
    for sid in db.scalars(select(sessions.c.id).where(sessions.c.user_id == user_id)):
        uuid.UUID(sid)  # session ids are UUIDs; anything else must not become a path
        d = (raw_root / sid).resolve()
        if d.parent != raw_root:
            raise RuntimeError("session raw path escapes DATA_DIR/raw")
        dirs.append(d)
    return dirs


def delete_user(db: Session, user_id: str, data_dir: Path) -> None:
    """Delete raw files, then every row of the user, then the user. Tokens die with the rows.

    Files go first: if anything fails, the transaction rolls back, the rows remain and
    the delete can be retried. Leaves one audit row with user_id NULL.
    """
    _active_user(db, user_id)
    try:
        for d in _raw_dirs(db, user_id, data_dir):
            if d.exists():
                shutil.rmtree(d)
        _revoke_all(db, user_id)
        for t in reversed(_user_tables()):
            db.execute(delete(t).where(t.c.user_id == user_id))
        db.execute(delete(User).where(User.id == user_id))
        audit(db, None, "account.delete")
        db.commit()
    except Exception:
        db.rollback()
        raise
    log.info("account deleted")

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
from typing import Any, NoReturn
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Table, Text, delete, func, or_, select, type_coerce, update
from sqlalchemy.orm import Session

from backend import security
from backend.config import get_settings
from backend.models import AuditLog, Base, Consent, Profile, RefreshToken, User
from backend.services.station_time import SETTINGS_KEY, offset_from_settings, validate_offset

log = logging.getLogger(__name__)

PASSWORD_MIN = 10
PASSWORD_MAX = 1024  # bounds hashing cost; not a policy value
DISPLAY_NAME_MAX = 128
CONSENT_SCOPES: tuple[str, ...] = ("checkins", "survey_answers", "raw_csi", "share_summaries")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Columns never exported, even to the account owner.
_EXPORT_EXCLUDE = {"password_hash", "token_sha256"}


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


class DemoDisabled(AccountError):
    code = "not_found"


class DemoProtected(AccountError):
    code = "demo_protected"


class DemoFull(AccountError):
    code = "demo_full"


class SignupClosed(AccountError):
    code = "signup_closed"


class TooManyAttempts(AccountError):
    code = "too_many_attempts"

    def __init__(self, retry_after: int) -> None:
        super().__init__("too many failed logins; try again later")
        self.retry_after = retry_after


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


def audit(db: Session, user_id: str | None, action: str, **details: Any) -> None:
    """Add an audit row (caller commits). details must hold no red-class values."""
    db.add(AuditLog(user_id=user_id, action=action, details=details))


def _issue_tokens(db: Session, user_id: str) -> AuthResult:
    s = get_settings()
    plaintext, digest = security.new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user_id,
            token_sha256=digest,
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
    cap = get_settings().signup_max_users
    if cap > 0:
        real = db.scalar(
            select(func.count()).select_from(User).where(User.is_synthetic.is_(False))
        )
        if (real or 0) >= cap:
            raise SignupClosed("this deployment has reached its account limit")
    user = User(email=email, password_hash=security.hash_password(password))
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id))
    result = _issue_tokens(db, user.id)
    audit(db, user.id, "auth.signup")
    db.commit()
    log.info("signup user_id=%s", user.id)
    return result


def login(
    db: Session,
    email: str,
    password: str,
    client_ip: str = "unknown",
    limiter: security.LoginLimiter | None = None,
) -> AuthResult:
    """Throttled per (email, client_ip) and per email (config.yaml auth:).

    A locked key is refused before any password check, so a locked attempt reveals nothing.
    Unknown and known emails are counted the same way, so throttling cannot be used to find
    out which emails exist.
    """
    limiter = limiter or security.get_login_limiter()
    key = email.strip().lower()
    wait = limiter.retry_after(key, client_ip)
    if wait is not None:
        raise TooManyAttempts(wait)
    try:
        email = normalize_email(email)
        user = db.scalar(select(User).where(User.email == email))
    except InvalidInput:
        user = None
    if user is None:
        security.burn_verify(password)
        _login_failed(db, None, key, client_ip, limiter)
    elif not security.verify_password(user.password_hash, password) or user.status != "active":
        audit(db, user.id, "auth.login_failed")
        _login_failed(db, user.id, key, client_ip, limiter)
    limiter.record_success(key, client_ip)
    result = _issue_tokens(db, user.id)
    audit(db, user.id, "auth.login")
    db.commit()
    log.info("login user_id=%s", user.id)
    return result


def _login_failed(
    db: Session, user_id: str | None, key: str, client_ip: str, limiter: security.LoginLimiter
) -> NoReturn:
    """Count the failure, audit a lockout when one starts, then refuse with the usual 401."""
    for scope in limiter.record_failure(key, client_ip):
        # Never the attempted email or the IP: the scope and window are enough to investigate.
        audit(db, user_id, "auth.lockout", scope=scope, window_s=limiter.window_s)
        log.warning("login lockout scope=%s user_id=%s", scope, user_id)
    db.commit()
    raise InvalidCredentials("invalid email or password")


def refresh(db: Session, refresh_token: str) -> AuthResult:
    """Rotate: the presented token is revoked and a new pair issued.

    Presenting an already-revoked token is treated as theft: every token of that user is revoked.
    """
    row = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_sha256 == security.hash_refresh_token(refresh_token)
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
        RefreshToken.token_sha256 == security.hash_refresh_token(refresh_token),
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
        "timezone": prof.timezone if prof else None,  # legacy, not used for night math
        "station_time_offset_min": offset_from_settings(prof.settings) if prof else None,
    }


def update_profile(db: Session, user_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Apply only the keys present in changes (display_name, timezone, station_time_offset_min).

    station_time_offset_min: optional station clock as minutes from UTC; None clears it (UTC).
    """
    _active_user(db, user_id)
    changes = dict(changes)
    unknown = set(changes) - {"display_name", "timezone", "station_time_offset_min"}
    if unknown:
        raise InvalidInput(f"unknown profile fields: {sorted(unknown)}")
    if "timezone" in changes:
        try:
            ZoneInfo(str(changes["timezone"]))
        except (ZoneInfoNotFoundError, ValueError):
            raise InvalidInput("unknown timezone") from None
    station_set = "station_time_offset_min" in changes
    if station_set:
        try:
            station_offset = validate_offset(changes.pop("station_time_offset_min"))
        except ValueError as exc:
            raise InvalidInput(str(exc)) from None
    name = changes.get("display_name")
    if name is not None and len(name) > DISPLAY_NAME_MAX:
        raise InvalidInput(f"display_name is longer than {DISPLAY_NAME_MAX} characters")
    prof = db.scalar(select(Profile).where(Profile.user_id == user_id))
    if prof is None:
        prof = Profile(user_id=user_id)
        db.add(prof)
    for k, v in changes.items():
        setattr(prof, k, v)
    if station_set:
        settings = dict(prof.settings or {})
        if station_offset is None:
            settings.pop(SETTINGS_KEY, None)
        else:
            settings[SETTINGS_KEY] = station_offset
        prof.settings = settings
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
            audit(
                db,
                user_id,
                "consent.change",
                scope=scope,
                granted=granted,
                policy_version=policy_version,
            )
    db.commit()
    return get_consents(db, user_id)


# --------------------------------------------------------------------------- export / delete


# Tables whose rows outlive the user with user_id set to NULL. Every other table with a
# user_id column is deleted with the user, whether its user_id is nullable or not.
ANONYMISED_TABLES = frozenset({"audit_log"})


def _user_tables() -> list[Table]:
    """Every table with a user_id column, parents before children."""
    return [t for t in Base.metadata.sorted_tables if "user_id" in t.c]


def _identifiers(db: Session, user_id: str) -> set[str]:
    """UUIDs that identify the user's data: the user id and their session ids.

    Content hashes are deliberately not used: identical files (an empty markers.csv, the
    same meta.json) hash the same for different users, so a hash would match their runs too.
    """
    ids = {user_id}
    if (s := Base.metadata.tables.get("sessions")) is not None:
        ids.update(db.scalars(select(s.c.id).where(s.c.user_id == user_id)))
    return ids


def _delete_runs_mentioning(db: Session, identifiers: set[str]) -> int:
    """Delete pipeline_runs whose parameters or log mention any identifier.

    Runs created by runs.create_run() carry no user_id; the user appears only inside
    parameters ({"session_id"} or {"user_id", "day"}). Every run kind is single-user, so a
    run that mentions the user is the user's run. Identifiers are UUIDs, which contain no
    LIKE wildcards.
    """
    runs = Base.metadata.tables.get("pipeline_runs")
    if runs is None or not identifiers:
        return 0
    cols = [type_coerce(runs.c[n], Text) for n in ("parameters", "log") if n in runs.c]
    for ident in identifiers:
        uuid.UUID(ident)  # raises ValueError for anything that is not a UUID
    cond = or_(*(c.like(f"%{ident}%") for c in cols for ident in sorted(identifiers)))
    return db.execute(delete(runs).where(cond)).rowcount or 0


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


def _attr_names(table: Table) -> dict[str, str]:
    """Column name -> ORM attribute name (display_name_enc -> display_name)."""
    for m in Base.registry.mappers:
        if m.local_table is table:
            return {c.name: key for key, c in m.columns.items()}
    return {}


def _rows(db: Session, table: Table, where: Any) -> list[dict[str, Any]]:
    names = _attr_names(table)
    cols = [
        c.label(names.get(c.name, c.name))
        for c in table.c
        if names.get(c.name, c.name) not in _EXPORT_EXCLUDE and c.name not in _EXPORT_EXCLUDE
    ]
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


def _inside_raw(stored: str, data_dir: Path, raw_root: Path) -> Path:
    """Resolve a stored path (relative to DATA_DIR, e.g. "raw/<uuid>") and require it to
    lie strictly inside DATA_DIR/raw."""
    p = Path(stored)
    p = (p if p.is_absolute() else data_dir / p).resolve()
    if p == raw_root or not p.is_relative_to(raw_root):
        raise ValueError("stored raw path is outside DATA_DIR/raw")
    return p


def _raw_paths(db: Session, user_id: str, data_dir: Path) -> list[Path]:
    """Everything on disk that belongs to the user: DATA_DIR/raw/<session_id>,
    sessions.raw_path and raw_files.path (both stored relative to DATA_DIR).
    Anything that would escape DATA_DIR/raw raises before a single file is touched."""
    tables = Base.metadata.tables
    sessions, raw_files = tables.get("sessions"), tables.get("raw_files")
    raw_root = (data_dir / "raw").resolve()
    paths: list[Path] = []
    if sessions is not None:
        has_raw_path = "raw_path" in sessions.c
        cols = [sessions.c.id] + ([sessions.c.raw_path] if has_raw_path else [])
        for row in db.execute(select(*cols).where(sessions.c.user_id == user_id)):
            uuid.UUID(row.id)  # session ids are UUIDs; anything else must not become a path
            paths.append(raw_root / row.id)
            if has_raw_path and row.raw_path:
                paths.append(_inside_raw(row.raw_path, data_dir, raw_root))
    if raw_files is not None and "path" in raw_files.c:
        for fp in db.scalars(select(raw_files.c.path).where(raw_files.c.user_id == user_id)):
            if fp:
                paths.append(_inside_raw(fp, data_dir, raw_root))
    return paths


DEMO_CREW = {  # visitor choice -> seeded synthetic template
    "iss-flight": "iss-flight@ex.com",
    "iss-aligned": "iss-aligned@ex.com",
    "iss-misaligned": "iss-misaligned@ex.com",
}


def demo_login(
    db: Session, crew: str | None = None, profile: dict[str, Any] | None = None
) -> AuthResult:
    """Tokens for a fresh private demo account, no password (Space Apps rule).

    Only when settings.demo_access is on, at most settings.demo_max_users visitors.
    - no choice: a copy of the default persona (settings.demo_email);
    - ``crew``: a copy of one NASA-calibrated ISS crew member (DEMO_CREW);
    - ``profile``: the visitor's own synthetic 14 nights from 5 answers (personas.seed_visitor).
    Templates are synthetic users only; real accounts can never be reached this way.
    """
    from backend.services import demo_pool, personas

    s = get_settings()
    if not s.demo_access:
        raise DemoDisabled("demo access is not enabled")
    try:
        if profile is not None:
            visitor, email = demo_pool.create_visitor(db, s.demo_max_users)
            db.add(Profile(user_id=visitor))
            db.commit()
            personas.seed_visitor(db, visitor, email, profile)
        else:
            email = DEMO_CREW.get(crew or "", s.demo_email)
            if crew is not None and crew not in DEMO_CREW:
                raise InvalidInput("unknown crew member")
            user = db.scalar(
                select(User).where(User.email == email, User.is_synthetic.is_(True))
            )
            if user is None or getattr(user, "deleted_at", None) is not None:
                raise UserNotFound("demo persona is not seeded")
            visitor = demo_pool.clone_user(db, user.id, s.demo_max_users)
    except demo_pool.DemoFull:
        db.rollback()
        raise DemoFull("the demo is full; please try again later") from None
    result = _issue_tokens(db, visitor)
    audit(db, visitor, "auth.demo_login")
    db.commit()
    return result


def delete_user(db: Session, user_id: str, data_dir: Path | None = None) -> None:
    """Delete raw files, then every row of the user, then the user. Tokens die with the rows.

    data_dir defaults to settings.data_dir (from .env). Files go first: if anything fails,
    the transaction rolls back, the rows remain and the delete can be retried. Audit rows
    stay with user_id NULL, plus one anonymous "account.delete" row; pipeline_runs that
    mention the user (by user_id column or inside parameters/log) are deleted.
    """
    from backend.services import demo_pool

    s = get_settings()
    if s.demo_access:
        demo = db.scalar(select(User).where(User.id == user_id, User.is_synthetic.is_(True)))
        # Seeded personas are shared templates; a visitor's own copy may be deleted.
        if demo is not None and not demo_pool.is_visitor(demo.email):
            raise DemoProtected("the shared demo account cannot be deleted")
    _active_user(db, user_id)
    data_dir = Path(data_dir if data_dir is not None else get_settings().data_dir)
    try:
        # Deepest first, so files inside an already-removed folder are simply skipped.
        for p in sorted(set(_raw_paths(db, user_id, data_dir)), key=lambda x: -len(x.parts)):
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
        identifiers = _identifiers(db, user_id)
        _revoke_all(db, user_id)
        for t in reversed(_user_tables()):
            if t.name in ANONYMISED_TABLES:
                db.execute(update(t).where(t.c.user_id == user_id).values(user_id=None))
            else:
                db.execute(delete(t).where(t.c.user_id == user_id))
        _delete_runs_mentioning(db, identifiers)
        db.execute(delete(User).where(User.id == user_id))
        audit(db, None, "account.delete")
        db.commit()
    except Exception:
        db.rollback()
        raise
    log.info("account deleted")

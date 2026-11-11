"""Password hashing, tokens and field encryption.

- Passwords: Argon2id (argon2-cffi defaults).
- Access tokens: short-lived HS256 JWTs signed with SECRET_KEY.
- Refresh tokens: random plaintext handed to the client once; only the sha256 is stored.
- Red-class fields: Fernet(FIELD_KEY). The key lives in the environment, never in the DB.
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import LargeBinary
from sqlalchemy.types import TypeDecorator

from backend.config import get_settings

_ALGORITHM = "HS256"
_ph = PasswordHasher()


class TokenError(Exception):
    """An access token is missing, malformed, expired or signed with another key."""


class FieldKeyMissing(RuntimeError):
    """FIELD_KEY is not set and we are not running under pytest."""


# --------------------------------------------------------------------------- passwords


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(h: str, pw: str) -> bool:
    try:
        return _ph.verify(h, pw)
    except (VerificationError, InvalidHashError):
        return False


# Used to spend the same time on unknown emails as on wrong passwords.
_DUMMY_HASH = _ph.hash(secrets.token_urlsafe(16))


def burn_verify(pw: str) -> None:
    verify_password(_DUMMY_HASH, pw)


# --------------------------------------------------------------------------- access tokens


def make_access_token(user_id: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
        "typ": "access",
    }
    return jwt.encode(claims, s.secret_key, algorithm=_ALGORITHM)


def decode_access_token(tok: str) -> str:
    """Return the user_id in a valid access token, else raise TokenError."""
    try:
        claims = jwt.decode(
            tok,
            get_settings().secret_key,
            algorithms=[_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.PyJWTError as e:
        raise TokenError("invalid access token") from e
    if claims.get("typ") != "access" or not isinstance(claims.get("sub"), str):
        raise TokenError("invalid access token")
    return claims["sub"]


# --------------------------------------------------------------------------- refresh tokens


def hash_refresh_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    """Return (plaintext, sha256). Store only the sha256."""
    plaintext = secrets.token_urlsafe(32)
    return plaintext, hash_refresh_token(plaintext)


# --------------------------------------------------------------------------- login throttling


class LoginLimiter:
    """In-process fixed-window counters of FAILED logins, per (email, ip) and per email.

    A window starts at a key's first failure and lasts ``window_s``. Once a key has reached its
    maximum inside the window, ``retry_after`` reports the seconds left until the window ends.
    A success clears only the (email, ip) key, so a legitimate login cannot reset the
    per-email count that an attacker on other IPs is building. Single process only: counts
    are lost on restart and not shared between workers (fine for the offline demo).
    """

    _PRUNE_AT = 10_000  # entries; expired windows are dropped when the table grows past this

    def __init__(
        self,
        window_s: int,
        max_per_email_ip: int,
        max_per_email: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window_s = window_s
        self._limits = {"email_ip": max_per_email_ip, "email": max_per_email}
        self._clock = clock
        self._lock = threading.Lock()
        self._windows: dict[tuple[str, ...], tuple[float, int]] = {}  # key -> (start, count)

    @staticmethod
    def _keys(email: str, ip: str) -> dict[str, tuple[str, ...]]:
        e = email.strip().lower()
        return {"email_ip": ("email_ip", e, ip), "email": ("email", e)}

    def _live(self, key: tuple[str, ...], now: float) -> tuple[float, int] | None:
        w = self._windows.get(key)
        if w is None or now >= w[0] + self.window_s:
            self._windows.pop(key, None)
            return None
        return w

    def retry_after(self, email: str, ip: str) -> int | None:
        """Seconds until a locked key's window ends, or None when login may proceed."""
        now = self._clock()
        with self._lock:
            waits = [
                w[0] + self.window_s - now
                for scope, key in self._keys(email, ip).items()
                if (w := self._live(key, now)) is not None and w[1] >= self._limits[scope]
            ]
        return max(1, math.ceil(max(waits))) if waits else None

    def record_failure(self, email: str, ip: str) -> list[str]:
        """Count one failure. Returns the scopes that became locked by this failure."""
        now = self._clock()
        newly_locked = []
        with self._lock:
            if len(self._windows) > self._PRUNE_AT:
                for key in list(self._windows):
                    self._live(key, now)
            for scope, key in self._keys(email, ip).items():
                start, count = self._live(key, now) or (now, 0)
                self._windows[key] = (start, count + 1)
                if count + 1 == self._limits[scope]:
                    newly_locked.append(scope)
        return newly_locked

    def record_success(self, email: str, ip: str) -> None:
        with self._lock:
            self._windows.pop(self._keys(email, ip)["email_ip"], None)


_limiter: LoginLimiter | None = None
_limiter_lock = threading.Lock()


def get_login_limiter() -> LoginLimiter:
    """The process-wide limiter, built from config.yaml ``auth:`` on first use."""
    global _limiter
    with _limiter_lock:
        if _limiter is None:
            from csi_core.config import get_config

            a = get_config().auth
            _limiter = LoginLimiter(
                a.login_window_s, a.max_failures_per_email_ip, a.max_failures_per_email
            )
        return _limiter


def reset_login_limiter(limiter: LoginLimiter | None = None) -> None:
    """Replace (tests) or forget (rebuilt from config on next use) the process limiter."""
    global _limiter
    with _limiter_lock:
        _limiter = limiter


# --------------------------------------------------------------------------- field encryption


def _under_pytest() -> bool:
    return "pytest" in sys.modules


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = get_settings().field_key
    if not key:
        if not _under_pytest():
            raise FieldKeyMissing(
                "FIELD_KEY is empty. Generate one with "
                '`python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"` and put it in .env'
            )
        # Tests only: an ephemeral per-process key. Data encrypted with it is unreadable later.
        return Fernet(Fernet.generate_key())
    return Fernet(key.encode())


def reset_key_cache() -> None:
    """Forget the cached Fernet (tests that change FIELD_KEY call this)."""
    _fernet.cache_clear()


def encrypt(b: bytes) -> bytes:
    return _fernet().encrypt(b)


def decrypt(b: bytes) -> bytes:
    try:
        return _fernet().decrypt(b)
    except InvalidToken as e:
        raise ValueError("cannot decrypt field: wrong FIELD_KEY or corrupted data") from e


class EncryptedJSON(TypeDecorator):
    """Any JSON-serialisable value, stored as a Fernet token. None stays NULL."""

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> bytes | None:
        if value is None:
            return None
        return encrypt(json.dumps(value, separators=(",", ":")).encode())

    def process_result_value(self, value: bytes | None, dialect: Any) -> Any:
        if value is None:
            return None
        return json.loads(decrypt(value))

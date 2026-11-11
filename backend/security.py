"""Password hashing, tokens and field encryption.

- Passwords: Argon2id (argon2-cffi defaults).
- Access tokens: short-lived HS256 JWTs signed with SECRET_KEY.
- Refresh tokens: random plaintext handed to the client once; only the sha256 is stored.
- Red-class fields: Fernet(FIELD_KEY). The key lives in the environment, never in the DB.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sys
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
                "`python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\"` and put it in .env"
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

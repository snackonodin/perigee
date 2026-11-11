"""FastAPI dependencies: a DB session per request and the authenticated user_id.

SessionLocal must be bound first: call backend.db.init_db() at app startup.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend import db as db_mod
from backend.errors import unauthorized
from backend.security import TokenError, decode_access_token
from backend.services.accounts import is_active_user

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    with db_mod.SessionLocal() as s:
        yield s


DbSession = Annotated[Session, Depends(get_db)]


def current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """user_id from a valid Bearer access token whose user still exists and is active.

    The DB check means a deleted or disabled account is locked out at once, not when the
    access token expires.
    """
    if creds is None or creds.scheme.lower() != "bearer":
        raise unauthorized()
    try:
        user_id = decode_access_token(creds.credentials)
    except TokenError:
        raise unauthorized("invalid or expired token") from None
    if not is_active_user(db, user_id):
        raise unauthorized("invalid or expired token")
    return user_id


CurrentUser = Annotated[str, Depends(current_user)]

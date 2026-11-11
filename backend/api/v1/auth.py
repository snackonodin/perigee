"""POST /api/v1/auth/signup | login | refresh | logout. Thin: logic is in services/accounts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from backend.deps import DbSession
from backend.errors import ERROR_RESPONSES, ApiError, unauthorized
from backend.services import accounts as svc

router = APIRouter(prefix="/api/v1", tags=["auth"], responses=ERROR_RESPONSES)

_STATUS: dict[type[svc.AccountError], int] = {
    svc.InvalidInput: 422,
    svc.EmailTaken: 409,
    svc.UserNotFound: 404,
}


@contextmanager
def account_errors() -> Iterator[None]:
    """Turn service errors into ErrorOut responses. Service messages never hold secrets."""
    try:
        yield
    except (svc.InvalidCredentials, svc.InvalidRefreshToken) as e:
        raise unauthorized(str(e)) from None
    except svc.AccountError as e:
        raise ApiError(_STATUS.get(type(e), 400), e.code, str(e)) from None


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignupIn(_In):
    email: str = Field(max_length=320)
    password: str = Field(min_length=svc.PASSWORD_MIN, max_length=svc.PASSWORD_MAX)


class LoginIn(_In):
    email: str = Field(max_length=320)
    password: str = Field(max_length=svc.PASSWORD_MAX)


class RefreshIn(_In):
    refresh_token: str = Field(min_length=1, max_length=256)


class TokenOut(BaseModel):
    user_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until the access token expires


def _out(r: svc.AuthResult) -> TokenOut:
    return TokenOut(
        user_id=r.user_id,
        access_token=r.access_token,
        refresh_token=r.refresh_token,
        token_type=r.token_type,
        expires_in=r.expires_in,
    )


@router.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, db: DbSession) -> TokenOut:
    with account_errors():
        return _out(svc.signup(db, body.email, body.password))


@router.post("/auth/login")
def login(body: LoginIn, db: DbSession) -> TokenOut:
    with account_errors():
        return _out(svc.login(db, body.email, body.password))


@router.post("/auth/refresh")
def refresh(body: RefreshIn, db: DbSession) -> TokenOut:
    with account_errors():
        return _out(svc.refresh(db, body.refresh_token))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshIn, db: DbSession) -> None:
    """Revoke the refresh token. Idempotent: an unknown token is not an error."""
    svc.logout(db, body.refresh_token)

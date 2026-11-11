from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.config import get_settings
from backend.deps import CurrentUser, DbSession
from backend.errors import install_error_handlers
from backend.services import accounts as acc

PW = "long enough password"


class Body(BaseModel):
    password: str
    n: int


@pytest.fixture
def client(engine):
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/whoami")
    def whoami(user_id: CurrentUser) -> dict[str, str]:
        return {"user_id": user_id}

    @app.post("/echo")
    def echo(body: Body, db: DbSession) -> dict[str, int]:
        return {"n": body.n}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret detail: password=hunter2-very-secret")

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _bearer(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def test_current_user_ok(client, db) -> None:
    r = acc.signup(db, "a@b.co", PW)
    res = client.get("/whoami", headers=_bearer(r.access_token))
    assert res.status_code == 200 and res.json() == {"user_id": r.user_id}


def _expired(user_id: str) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": user_id,
        "iat": now - timedelta(hours=1),
        "exp": now - timedelta(minutes=1),
        "typ": "access",
    }
    return jwt.encode(claims, get_settings().secret_key, algorithm="HS256")


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic YTpi"},
        _bearer("not.a.jwt"),
    ],
    ids=["missing", "basic", "garbage"],
)
def test_current_user_rejects(client, headers) -> None:
    res = client.get("/whoami", headers=headers)
    assert res.status_code == 401
    assert res.json()["error"] == "unauthorized"
    assert res.headers["www-authenticate"] == "Bearer"


def test_expired_and_deleted_user_rejected(client, db) -> None:
    r = acc.signup(db, "a@b.co", PW)
    assert client.get("/whoami", headers=_bearer(_expired(r.user_id))).status_code == 401
    acc.delete_user(db, r.user_id)
    res = client.get("/whoami", headers=_bearer(r.access_token))  # still unexpired JWT
    assert res.status_code == 401


def test_validation_error_does_not_echo_input(client) -> None:
    res = client.post("/echo", json={"password": "hunter2-very-secret", "n": "not-int"})
    assert res.status_code == 422
    body = res.json()
    assert body == {"error": "validation_error", "message": "invalid request", "fields": ["n"]}
    assert "hunter2" not in res.text


def test_unhandled_error_is_generic(client, caplog) -> None:
    res = client.get("/boom")
    assert res.status_code == 500
    assert res.json() == {"error": "internal_error", "message": "internal server error"}
    assert "Traceback" not in res.text and "hunter2" not in res.text
    assert "hunter2" not in caplog.text


def test_unknown_route_uses_errorout(client) -> None:
    res = client.get("/nope")
    assert res.status_code == 404 and res.json()["error"] == "not_found"

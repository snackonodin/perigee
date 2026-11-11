"""ACC-8: login throttling (fixed windows per (email, ip) and per email)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from backend import security
from backend.models import AuditLog
from backend.security import LoginLimiter
from backend.services import accounts as acc
from csi_core.config import get_config

PW = "long enough password"


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def lim(clock) -> LoginLimiter:
    return LoginLimiter(window_s=60, max_per_email_ip=3, max_per_email=5, clock=clock)


# --------------------------------------------------------------------------- limiter unit


def test_locks_after_max_per_email_ip(lim, clock) -> None:
    for _ in range(2):
        lim.record_failure("a@b.co", "1.1.1.1")
    assert lim.retry_after("a@b.co", "1.1.1.1") is None
    assert lim.record_failure("A@B.co ", "1.1.1.1") == ["email_ip"]  # case/space-insensitive
    clock.t += 10
    assert lim.retry_after("a@b.co", "1.1.1.1") == 50
    assert lim.retry_after("a@b.co", "2.2.2.2") is None  # other IP still allowed
    clock.t += 50
    assert lim.retry_after("a@b.co", "1.1.1.1") is None  # window over


def test_per_email_limit_spans_ips(lim) -> None:
    newly = [lim.record_failure("a@b.co", f"10.0.0.{i}") for i in range(5)]
    assert newly[-1] == ["email"] and not any(newly[:-1])
    assert lim.retry_after("a@b.co", "10.0.0.99") is not None  # a fresh IP is locked too
    assert lim.retry_after("other@b.co", "10.0.0.1") is None


def test_success_clears_only_email_ip(lim) -> None:
    for i in range(4):
        lim.record_failure("a@b.co", f"10.0.0.{i}")
    lim.record_failure("a@b.co", "1.1.1.1")  # 5th: email scope now locked
    lim.record_success("a@b.co", "1.1.1.1")
    assert lim.retry_after("a@b.co", "1.1.1.1") is not None  # the per-email lock remains


def test_limiter_built_from_config() -> None:
    a = get_config().auth
    lim = security.get_login_limiter()
    assert lim.window_s == a.login_window_s
    assert security.get_login_limiter() is lim


# --------------------------------------------------------------------------- service


def test_service_lockout_audited_and_refuses_before_password_check(db, lim, monkeypatch) -> None:
    r = acc.signup(db, "a@b.co", PW)
    for _ in range(3):
        with pytest.raises(acc.InvalidCredentials):
            acc.login(db, "a@b.co", "wrong password!", client_ip="1.1.1.1", limiter=lim)
    calls = []
    monkeypatch.setattr(security, "verify_password", lambda *a: calls.append(a) or True)
    with pytest.raises(acc.TooManyAttempts) as e:
        acc.login(db, "a@b.co", PW, client_ip="1.1.1.1", limiter=lim)  # right password
    assert e.value.retry_after == 60 and calls == []
    lockouts = db.scalars(select(AuditLog).where(AuditLog.action == "auth.lockout")).all()
    assert len(lockouts) == 1 and lockouts[0].user_id == r.user_id
    assert lockouts[0].details == {"scope": "email_ip", "window_s": 60}
    assert "1.1.1.1" not in repr(lockouts[0].details)


def test_unknown_email_throttled_identically(db, lim) -> None:
    """No enumeration: an unknown email fails, locks and audits the same way (user_id NULL)."""
    acc.signup(db, "a@b.co", PW)
    outcomes = {}
    for email in ("a@b.co", "ghost@b.co"):
        seen = []
        for _ in range(4):
            try:
                acc.login(db, email, "wrong password!", client_ip="9.9.9.9", limiter=lim)
            except acc.AccountError as e:
                seen.append((type(e).__name__, str(e)))
        outcomes[email] = seen
    assert outcomes["a@b.co"] == outcomes["ghost@b.co"]
    assert outcomes["a@b.co"][-1][0] == "TooManyAttempts"


def test_success_resets_email_ip_count(db, lim) -> None:
    acc.signup(db, "a@b.co", PW)
    for _ in range(2):
        with pytest.raises(acc.InvalidCredentials):
            acc.login(db, "a@b.co", "wrong password!", client_ip="1.1.1.1", limiter=lim)
    acc.login(db, "a@b.co", PW, client_ip="1.1.1.1", limiter=lim)
    for _ in range(2):  # would be the 3rd and 4th failure without the reset
        with pytest.raises(acc.InvalidCredentials):
            acc.login(db, "a@b.co", "wrong password!", client_ip="1.1.1.1", limiter=lim)


# --------------------------------------------------------------------------- route


def test_route_429_with_retry_after(api, lim, clock) -> None:
    security.reset_login_limiter(lim)
    api.post("/api/v1/auth/signup", json={"email": "a@b.co", "password": PW})
    bad = {"email": "a@b.co", "password": "wrong password!"}
    assert [api.post("/api/v1/auth/login", json=bad).status_code for _ in range(3)] == [401] * 3
    res = api.post("/api/v1/auth/login", json={"email": "a@b.co", "password": PW})
    assert res.status_code == 429
    assert res.headers["retry-after"] == "60"
    assert res.json() == {
        "error": "too_many_attempts",
        "message": "too many failed logins; try again later",
    }
    clock.t += 61
    assert (
        api.post("/api/v1/auth/login", json={"email": "a@b.co", "password": PW}).status_code == 200
    )

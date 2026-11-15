"""Real ESP32 captures (seeds/real_sessions): demo accounts only, host-measured, intact."""

from __future__ import annotations

import hashlib

from sqlalchemy import update

from backend.models import User
from backend.services import accounts as acc
from backend.services import real_sessions as rs
from tests.api.conftest import data_dir, db, engine  # noqa: F401  (fixtures)

PW = "long enough password"


def _user(db, email, synthetic):  # noqa: F811
    uid = acc.signup(db, email, PW).user_id
    if synthetic:
        db.execute(update(User).where(User.id == uid).values(is_synthetic=True))
    db.commit()
    return uid


def test_demo_account_sees_the_saved_captures_with_host_time_and_accuracy(db):  # noqa: F811
    uid = _user(db, "demo-x@example.invalid", True)
    docs = rs.list_for(db, uid)
    assert len(docs) >= 2
    for d in docs:
        assert d["measured_by"].startswith("Host laptop") and d["measured_at"]
        assert min(d["accuracy_pct"].values()) > 70
        assert d["truth"]["bpm"] and d["windows"]


def test_real_account_sees_none_and_cannot_download(db):  # noqa: F811
    real = _user(db, "real@ex.com", False)
    assert rs.list_for(db, real) == []
    assert rs.capture_path(db, real, "theta0_alt_position_manual_1min") is None


def test_download_is_the_unchanged_capture_and_ids_are_checked(db):  # noqa: F811
    uid = _user(db, "demo-y@example.invalid", True)
    for d in rs.list_for(db, uid):
        p = rs.capture_path(db, uid, d["id"])
        assert p is not None
        assert hashlib.sha256(p.read_bytes()).hexdigest() == d["source"]["capture_sha256"]
    assert rs.capture_path(db, uid, "../config") is None
    assert rs.capture_path(db, uid, "missing") is None


def test_samples_route_requires_auth():
    from fastapi.testclient import TestClient

    from backend.main import create_app

    with TestClient(create_app()) as c:
        assert c.get("/api/v1/monitor/samples").status_code == 401
        assert c.get("/api/v1/monitor/samples/x/capture.csv").status_code == 401

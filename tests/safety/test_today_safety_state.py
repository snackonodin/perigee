"""GET /today carries the server-driven safety lock (2026-11-13 decision)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import db as db_mod
from backend.config import get_settings
from backend.main import create_app
from backend.models import Base
from backend.services import accounts, guidance, surveys


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    d = tmp_path / "astro-data"
    d.mkdir()
    monkeypatch.setenv("DATA_DIR", str(d))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{d / 'db' / 'astro.db'}")
    get_settings.cache_clear()
    eng = db_mod.init_db()
    Base.metadata.create_all(eng)
    with db_mod.SessionLocal() as s:
        surveys.load_catalog(s)
        guidance.load_guidance_cards(s)
    with TestClient(create_app(with_lifespan=False), raise_server_exceptions=False) as c:
        yield c
    eng.dispose()
    db_mod.SessionLocal.configure(bind=None)
    get_settings.cache_clear()


def _user(email: str) -> dict[str, str]:
    with db_mod.SessionLocal() as s:
        r = accounts.signup(s, email, "long enough password")
        accounts.set_consents(s, r.user_id, {"survey_answers": True, "checkins": True}, "t1")
    return {"Authorization": f"Bearer {r.access_token}"}


def _phq9(client: TestClient, h: dict[str, str], answers: dict) -> dict:
    body = {"instrument_id": "phq9", "instrument_version": "1.0", "answers": answers}
    return client.post("/api/v1/responses", json=body, headers=h).json()


def _today(client: TestClient, h: dict[str, str]) -> dict:
    r = client.get("/api/v1/today", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


EIGHT = {f"phq9_{i}": 1 for i in range(1, 9)}


def test_today_safety_lock_is_server_driven_and_user_scoped(client):
    a, b = _user("a@example.test"), _user("b@example.test")
    assert _today(client, a)["safety_screen_required"] is False

    _phq9(client, a, {**EIGHT, "phq9_9": 2})  # positive item 9
    t = _today(client, a)
    assert t["safety_screen_required"] is True and t["missing_safety_item"] is None
    assert _today(client, b)["safety_screen_required"] is False  # user B never sees A's flag

    _phq9(client, a, EIGHT)  # missing item 9 keeps the lock and names the item
    t = _today(client, a)
    assert t["safety_screen_required"] is True and t["missing_safety_item"] == "phq9_9"

    _phq9(client, a, {**EIGHT, "phq9_9": 0})  # later clean, complete submission clears it
    t = _today(client, a)
    assert t["safety_screen_required"] is False and t["missing_safety_item"] is None


def test_unstored_positive_submission_still_locks_today(client):
    a = _user("c@example.test")
    _phq9(client, a, {"phq9_9": 1})  # invalid (items 1-8 missing): not stored, event recorded
    assert _today(client, a)["safety_screen_required"] is True

"""POST /responses safety contract (2026-11-13 decision).

Safety is decided before any DB write or scoring. Item 9 positive or missing sets the
top-level safety_screen_required, the submission is still stored with safety_flag, and a
storage failure never suppresses the safety screen.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import db as db_mod
from backend.config import get_settings
from backend.main import create_app
from backend.models import Base, SurveyResponseRow
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


@pytest.fixture
def headers(client) -> dict[str, str]:
    with db_mod.SessionLocal() as s:
        r = accounts.signup(s, "safety@example.test", "long enough password")
        accounts.set_consents(s, r.user_id, {"survey_answers": True, "checkins": True}, "t1")
    return {"Authorization": f"Bearer {r.access_token}"}


def _post(client: TestClient, headers: dict[str, str], answers: dict) -> object:
    body = {
        "instrument_id": "phq9",
        "instrument_version": "1.0",
        "administered_at": "2026-11-10T08:00:00Z",
        "answers": answers,
    }
    return client.post("/api/v1/responses", json=body, headers=headers)


def _eight(rest: int = 1) -> dict[str, int]:
    return {f"phq9_{i}": rest for i in range(1, 9)}


def test_positive_item9_is_stored_with_flag_and_top_level_screen(client, headers, caplog):
    caplog.set_level(logging.DEBUG)
    r = _post(client, headers, {**_eight(), "phq9_9": 2})
    assert r.status_code == 200
    j = r.json()
    assert j["safety_screen_required"] is True and j["missing_safety_item"] is None
    assert j["ok"] is True and j["stored"] is True and j["total"] == 10
    with db_mod.SessionLocal() as s:
        row = s.get(SurveyResponseRow, j["id"])
        assert row.safety_flag is True and row.answers["phq9_9"] == 2
    assert "safety flag fired" in caplog.text
    assert "phq9_9" not in caplog.text  # only the fact that a flag fired


def test_missing_item9_is_stored_and_names_the_missing_item(client, headers):
    r = _post(client, headers, _eight())
    assert r.status_code == 200
    j = r.json()
    assert j["safety_screen_required"] is True
    assert j["missing_safety_item"] == "phq9_9"
    assert j["ok"] is True and j["stored"] is True
    assert j["total"] is None and j["scores"]["incomplete"] is True  # no invented total
    with db_mod.SessionLocal() as s:
        row = s.get(SurveyResponseRow, j["id"])
        assert row.safety_flag is True and "phq9_9" not in row.answers


def test_storage_failure_still_requires_safety_screen(client, headers, monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(surveys, "_store_survey", fail)
    for answers in ({**_eight(), "phq9_9": 1}, _eight()):
        r = _post(client, headers, answers)
        assert r.status_code == 500
        j = r.json()
        assert j["safety_screen_required"] is True
        assert j["ok"] is False and j["error"] == "storage" and j["stored"] is False

"""Persona from the Mini-IPIP quiz: ready at once, engine-scored, per-user, no score effect."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import db as db_mod
from backend.config import get_settings
from backend.main import create_app
from backend.models import Base, Profile
from backend.services import accounts, surveys

PW = "long enough password"
# E high, A high, C high, N low, O high (engine reverses items 2,4,...,20).
ANSWERS = [4, 2, 4, 2, 5, 1, 4, 2, 4, 2, 5, 1, 2, 4, 2, 4, 5, 1, 4, 2]


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
    with TestClient(create_app(with_lifespan=False), raise_server_exceptions=False) as c:
        yield c
    eng.dispose()
    db_mod.SessionLocal.configure(bind=None)
    get_settings.cache_clear()


def _user(email: str, consents: bool = True) -> tuple[str, dict[str, str]]:
    with db_mod.SessionLocal() as s:
        r = accounts.signup(s, email, PW)
        if consents:
            accounts.set_consents(s, r.user_id, {"survey_answers": True, "checkins": True}, "t1")
    return r.user_id, {"Authorization": f"Bearer {r.access_token}"}


def _quiz(client, headers, values=ANSWERS):
    body = {
        "instrument_id": "mini_ipip",
        "instrument_version": "1.0",
        "administered_at": "2026-11-10T08:00:00Z",
        "answers": {f"mini_ipip_{i}": v for i, v in enumerate(values, 1)},
    }
    return client.post("/api/v1/responses", json=body, headers=headers)


def test_persona_empty_before_quiz(client) -> None:
    _, h = _user("a@example.test")
    j = client.get("/api/v1/persona", headers=h).json()
    assert j["available"] is False and j["traits"] == {} and j["persona_matrix"] is None


def test_persona_requires_auth(client) -> None:
    assert client.get("/api/v1/persona").status_code == 401


def test_quiz_gives_persona_immediately_without_nights(client) -> None:
    _, h = _user("a@example.test")
    res = _quiz(client, h)
    assert res.status_code == 200, res.text
    assert res.json()["scores"]["traits"] == {"E": 16.0, "A": 18.0, "C": 18.0, "N": 8.0, "O": 18.0}
    j = client.get("/api/v1/persona", headers=h).json()
    assert j["available"] is True and j["source"] == "mini_ipip"
    assert j["traits"]["C"] == 18.0
    assert j["persona_matrix"] == {
        "stability_score": 17.0, "agency_score": 17.0, "quadrant_name": "Autonomous Pioneer"
    }


def test_retake_replaces_traits(client) -> None:
    _, h = _user("a@example.test")
    _quiz(client, h)
    _quiz(client, h, [3] * 20)
    j = client.get("/api/v1/persona", headers=h).json()
    assert j["traits"] == {"E": 12.0, "A": 12.0, "C": 12.0, "N": 12.0, "O": 12.0}


def test_traits_saved_even_without_answer_consent_but_answers_are_not(client) -> None:
    _, h = _user("a@example.test", consents=False)
    res = _quiz(client, h).json()
    assert res["answers_retained"] is False
    assert client.get("/api/v1/persona", headers=h).json()["available"] is True


def test_user_b_cannot_see_user_a_persona(client) -> None:
    _, ha = _user("a@example.test")
    _, hb = _user("b@example.test")
    _quiz(client, ha)
    assert client.get("/api/v1/persona", headers=hb).json()["available"] is False


def test_quiz_is_not_a_load_measure(client) -> None:
    uid, h = _user("a@example.test")
    _quiz(client, h)
    with db_mod.SessionLocal() as s:
        out = surveys.weekly_indices(s, uid, date(2026, 11, 9))
    assert not any(k.startswith("mini_ipip") for k in out)


def test_nightly_payload_carries_quiz_traits(client) -> None:
    from types import SimpleNamespace

    from backend.services.context_engine import build_payload

    uid, h = _user("a@example.test")
    _quiz(client, h)
    night = SimpleNamespace(
        rr_med=14.0, rr_var=0.2, restless_frac=0.1, quality=0.9, presence_hours=6.0
    )
    with db_mod.SessionLocal() as s:
        payload, _ = build_payload(s, uid, date(2026, 11, 11), night)
        assert s.query(Profile).filter_by(user_id=uid).one().settings["traits"]["N"] == 8.0
    assert payload["persona"]["traits"]["E"] == 16.0

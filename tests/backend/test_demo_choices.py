"""Public demo choices: copy an ISS crew member, or synthesise the visitor's own nights."""

from __future__ import annotations

import pytest
from sqlalchemy import select, update

from backend.config import get_settings
from backend.models import NightFeaturesRow, SurveyResponseRow, User
from backend.services import accounts as acc
from backend.services import surveys
from tests.api.conftest import api, data_dir, db, engine  # noqa: F401  (fixtures)

PROFILE = {"sleep_hours": 6.0, "regularity": 2, "stress": 3, "mood": 1, "recent_change": True}


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS", "1")
    monkeypatch.setenv("DEMO_MAX_USERS", "3")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()



def test_own_answers_give_a_private_14_night_history(api, db, demo_on) -> None:  # noqa: F811
    surveys.load_catalog(db)
    res = api.post("/api/v1/auth/demo", json={"profile": PROFILE})
    assert res.status_code == 200, res.text
    uid = res.json()["user_id"]
    db.expire_all()
    nights = db.scalars(select(NightFeaturesRow).where(NightFeaturesRow.user_id == uid)).all()
    assert len(nights) == 14
    insts = {r.instrument_id for r in db.scalars(
        select(SurveyResponseRow).where(SurveyResponseRow.user_id == uid))}
    assert "phq9" not in insts  # the safety item is never simulated
    assert db.get(User, uid).is_synthetic


def test_bad_answers_are_rejected(api, db, demo_on) -> None:  # noqa: F811
    bad = {**PROFILE, "sleep_hours": 15}
    assert api.post("/api/v1/auth/demo", json={"profile": bad}).status_code == 422
    both = {"profile": PROFILE, "crew": "iss-flight"}
    assert api.post("/api/v1/auth/demo", json=both).status_code == 422


def test_crew_copy_needs_a_seeded_template(api, db, demo_on) -> None:  # noqa: F811
    assert api.post("/api/v1/auth/demo", json={"crew": "iss-flight"}).status_code == 404
    uid = acc.signup(db, "iss-flight@ex.com", "long enough password").user_id
    db.execute(update(User).where(User.id == uid).values(is_synthetic=True))
    db.commit()
    res = api.post("/api/v1/auth/demo", json={"crew": "iss-flight"})
    assert res.status_code == 200 and res.json()["user_id"] != uid
    assert api.post("/api/v1/auth/demo", json={"crew": "nobody"}).status_code == 422


def test_cap_covers_both_kinds(api, db, demo_on) -> None:  # noqa: F811
    surveys.load_catalog(db)
    for _ in range(3):
        assert api.post("/api/v1/auth/demo", json={"profile": PROFILE}).status_code == 200
    res = api.post("/api/v1/auth/demo", json={"profile": PROFILE})
    assert res.status_code == 503 and res.json()["error"] == "demo_full"

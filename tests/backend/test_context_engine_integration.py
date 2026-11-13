"""Backend integration guarantees at the Context Engine boundary."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.v1 import responses
from backend.deps import current_user, get_db
from backend.models import (
    CheckinDaily,
    ContextEngineNight,
    NightFeaturesRow,
    Profile,
    SafetyEvent,
    SurveyResponseRow,
    User,
)
from backend.services.context_engine import run_night
from backend.services.readouts import today as get_today


@pytest.fixture
def db_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from backend.models import Base

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


def _night(user_id: str, day: date, rr: float = 14.0) -> NightFeaturesRow:
    return NightFeaturesRow(
        user_id=user_id,
        date=day,
        rr_med=rr,
        rr_var=0.5,
        presence_hours=7.0,
        restless_frac=0.05,
        quality=0.9,
        valid=True,
        session_ids=[],
        source_kind="csi",
    )


def test_nightly_state_is_saved_reloaded_and_same_night_is_idempotent(db_factory):
    user_id = "context-user"
    with db_factory() as db:
        db.add(User(id=user_id, email="context@example.invalid", status="active"))
        db.add(Profile(user_id=user_id, timezone="UTC", settings={}))
        db.commit()

        first_day = date(2026, 11, 10)
        first = run_night(db, user_id, first_day, _night(user_id, first_day), None)
        first_state = first["state"]
        assert first_state["schema_version"] == "1"

        # A rerun reads the preceding night again; it does not apply the same
        # night twice to CUSUM/history.
        repeated = run_night(db, user_id, first_day, _night(user_id, first_day), None)
        assert repeated["state"] == first_state
        assert (
            db.scalar(
                select(func.count())
                .select_from(ContextEngineNight)
                .where(ContextEngineNight.user_id == user_id)
            )
            == 1
        )

        second_day = first_day + timedelta(days=1)
        second = run_night(db, user_id, second_day, _night(user_id, second_day), None)
        assert second["state"]["schema_version"] == "1"
        assert len(second["state"]["history"]) == len(first_state["history"]) + 1
        saved = db.scalar(
            select(ContextEngineNight).where(
                ContextEngineNight.user_id == user_id, ContextEngineNight.date == second_day
            )
        )
        assert saved is not None
        assert saved.state_json == second["state"]
        assert saved.output_json == second
        assert saved.engine_revision
        assert get_today(db, user_id, on=second_day)["context_engine"] == second


@pytest.mark.parametrize("item9", [1, {}, {"phq9_9": None}, {"phq9_9": "bad"}, {"phq9_9": "1"}])
def test_response_safety_screen_is_top_level_for_incomplete_phq9(db_factory, item9):
    user_id = "safety-user"
    app = FastAPI()
    app.include_router(responses.router)
    with db_factory() as setup:
        setup.add(User(id=user_id, email="safety@example.invalid", status="active"))
        setup.commit()

    def session_dependency():
        with db_factory() as session:
            yield session

    app.dependency_overrides[get_db] = session_dependency
    app.dependency_overrides[current_user] = lambda: user_id
    with TestClient(app) as client:
        answers = {"phq9_9": item9} if not isinstance(item9, dict) else item9
        response = client.post(
            "/api/v1/responses", json={"instrument_id": "phq9", "answers": answers}
        )
    assert response.status_code == 200
    result = response.json()
    # 2026-11-13 contract: safety decided first and returned at the top level; these
    # payloads are otherwise invalid (items 1-8 missing), so nothing is stored.
    assert result["safety_screen_required"] is True and result["crisis"] is True
    assert result["safety"]["show"] is (item9 != {})
    assert result["missing_safety_item"] == ("phq9_9" if item9 == {} else None)
    assert result["stored"] is False and result["answers_retained"] is False
    assert result["id"] is None and result["total"] is None and result["scores"] is None

    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(SurveyResponseRow)) == 0
        assert db.scalar(select(func.count()).select_from(CheckinDaily)) == 0
        assert db.scalar(
            select(func.count()).select_from(SafetyEvent).where(SafetyEvent.user_id == user_id)
        ) == (0 if item9 == {} else 1)  # events record positive answers only

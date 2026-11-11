"""DB-backed survey functions against the real backend.models (merged from
feat/db-ingest) on an in-memory SQLite engine from backend.db (foreign keys on).

Answers are encrypted by the real EncryptedJSON type (backend.security); under
pytest FIELD_KEY falls back to a per-process key.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend import security
from backend.db import get_engine
from backend.models import (
    Base,
    CheckinDaily,
    Consent,
    Instrument,
    SafetyEvent,
    SurveyResponseRow,
    User,
)
from backend.schemas.contracts import SurveyResponse
from backend.services import surveys
from backend.services.surveys import SubmissionError, submit_response

USERS = ("u1", "u2", "userA", "userB")


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture()
def db():
    engine = get_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all(User(id=u, email=f"{u}@example.test", is_synthetic=True) for u in USERS)
        s.flush()
        for uid in USERS:
            for scope in ("survey_answers", "checkins"):
                s.add(Consent(user_id=uid, scope=scope, granted=True, policy_version="test"))
        s.commit()
        surveys.load_catalog(s)
        yield s
    engine.dispose()


def _resp(user: str, inst: str, answers: dict[str, int], version: str = "1.0", when=None):
    return SurveyResponse(
        user_id=user,
        instrument_id=inst,
        instrument_version=version,
        administered_at=when or _now(),
        answers=answers,
    )


def _at(y: int, mo: int, d: int, h: int = 12) -> datetime:
    return datetime(y, mo, d, h, tzinfo=UTC)


def _phq9(item9: int, rest: int = 1) -> dict[str, int]:
    a = {f"phq9_{i}": rest for i in range(1, 9)}
    a["phq9_9"] = item9
    return a


# --------------------------------------------------------------------------- catalog


def test_load_catalog_idempotent(db) -> None:
    surveys.load_catalog(db)
    surveys.load_catalog(db)
    assert db.query(Instrument).count() == 6
    row = db.scalars(select(Instrument).where(Instrument.instrument_id == "phq9")).one()
    assert row.version == "1.0" and row.source_url and row.definition["id"] == "phq9"
    assert surveys.get_instrument(db, "who5")["scoring"]["method"] == "sum_x4"
    with pytest.raises(surveys.UnknownInstrument):
        surveys.get_instrument(db, "nope")


# --------------------------------------------------------------------------- submit


def test_submit_scores_and_stores(db) -> None:
    out = submit_response(db, "u1", _resp("u1", "phq9", _phq9(0)))
    assert out["total"] == 8
    assert out["scores"]["band"] == "mild"
    assert out["safety"] == {"show": False, "reason": None, "resources": []}
    row = db.get(SurveyResponseRow, out["id"])
    assert row.user_id == "u1" and row.total == 8
    assert row.answers == _phq9(0)  # decrypted transparently by EncryptedJSON
    assert row.scores["band"] == "mild"
    assert db.query(SafetyEvent).count() == 0


def test_item9_positive_returns_safety_and_minimal_event(db) -> None:
    out = submit_response(db, "u1", _resp("u1", "phq9", _phq9(1)))
    assert out["safety"]["show"] is True and out["safety"]["resources"]
    events = db.query(SafetyEvent).all()
    assert len(events) == 1
    ev = events[0]
    assert (ev.user_id, ev.source, ev.reason) == ("u1", "survey:phq9", "safety_item")
    assert ev.details_enc is None  # minimal: nothing about the answers
    cols = {c.name for c in SafetyEvent.__table__.columns}
    assert not any("answer" in c for c in cols)


def test_safety_is_synchronous_no_job_or_queue(db, monkeypatch) -> None:
    # Any attempt to reach a runner/queue would fail the test.

    monkeypatch.setitem(sys.modules, "backend.services.runs", None)
    out = submit_response(db, "u1", _resp("u1", "phq9", _phq9(2)))
    assert out["safety"]["show"] is True


def test_safety_survives_invalid_answers(db) -> None:
    # Item 9 positive but other items missing: submission fails, safety still shown and stored.
    with pytest.raises(SubmissionError) as exc:
        submit_response(db, "u1", _resp("u1", "phq9", {"phq9_9": 3}))
    assert exc.value.kind == "invalid"
    assert exc.value.safety.show is True
    assert db.query(SafetyEvent).count() == 1
    assert db.query(SurveyResponseRow).count() == 0


def test_safety_survives_storage_failure(db, monkeypatch) -> None:
    real_add = db.add

    def add(obj):
        if isinstance(obj, SurveyResponseRow):
            raise RuntimeError("disk full")
        return real_add(obj)

    monkeypatch.setattr(db, "add", add)
    with pytest.raises(SubmissionError) as exc:
        submit_response(db, "u1", _resp("u1", "phq9", _phq9(1)))
    assert exc.value.kind == "storage" and exc.value.safety.show is True
    assert db.query(SafetyEvent).count() == 1


def test_safety_survives_safety_event_storage_failure(db, monkeypatch) -> None:
    real_add = db.add

    def add(obj):
        if isinstance(obj, SafetyEvent):
            raise RuntimeError("locked")
        return real_add(obj)

    monkeypatch.setattr(db, "add", add)
    out = submit_response(db, "u1", _resp("u1", "phq9", _phq9(1)))
    assert out["safety"]["show"] is True


def test_version_mismatch_and_unknown_instrument(db) -> None:
    with pytest.raises(SubmissionError) as exc:
        submit_response(db, "u1", _resp("u1", "phq2", {"phq2_1": 0, "phq2_2": 0}, version="9"))
    assert exc.value.kind == "invalid"
    with pytest.raises(SubmissionError) as exc:
        submit_response(db, "u1", _resp("u1", "nope", {"x": 1}))
    assert exc.value.kind == "unknown_instrument" and exc.value.safety.show is False


def test_user_mismatch_is_forbidden(db) -> None:
    with pytest.raises(SubmissionError) as exc:
        submit_response(db, "u1", _resp("u2", "phq2", {"phq2_1": 0, "phq2_2": 0}))
    assert exc.value.kind == "forbidden"
    assert db.query(SurveyResponseRow).count() == 0


def test_answers_hmac_empty_with_consent(db) -> None:
    out = submit_response(db, "u1", _resp("u1", "phq2", {"phq2_1": 0, "phq2_2": 1}))
    assert db.get(SurveyResponseRow, out["id"]).answers_hmac is None


def test_answers_encrypted_at_rest(db) -> None:
    out = submit_response(db, "u1", _resp("u1", "phq9", _phq9(0, rest=2)))
    raw = db.execute(
        text("SELECT answers_enc FROM survey_responses WHERE id = :id"), {"id": out["id"]}
    ).scalar_one()
    assert raw.startswith(b"gAAAAA")  # Fernet token
    assert json.loads(security.decrypt(raw)) == _phq9(0, rest=2)
    assert b"phq9_" not in raw


def test_logs_contain_no_answer_values(db, caplog) -> None:
    answers = _phq9(3, rest=2)
    sa_logger = logging.getLogger("sqlalchemy.engine")
    old = sa_logger.level
    sa_logger.setLevel(logging.INFO)  # SQL statements and bound parameters
    try:
        with caplog.at_level(logging.DEBUG):
            submit_response(db, "u1", _resp("u1", "phq9", answers))
            with pytest.raises(SubmissionError):
                submit_response(db, "u1", _resp("u1", "phq9", {"phq9_9": 2, "phq9_1": 7}))
    finally:
        sa_logger.setLevel(old)
    assert caplog.records, "expected some log output to inspect"
    blob = "\n".join(
        r.getMessage() + repr(r.args) + str(getattr(r, "exc_text", "")) for r in caplog.records
    )
    assert "phq9_" not in blob  # no item keys, so no key/value pairs
    assert json.dumps(answers) not in blob
    assert "'answers': {" not in blob


def test_safety_checked_before_validation_with_bad_option(db) -> None:
    answers = _phq9(1)
    answers["phq9_3"] = 9  # not an allowed option
    with pytest.raises(SubmissionError) as exc:
        submit_response(db, "u1", _resp("u1", "phq9", answers))
    assert exc.value.kind == "invalid"
    assert exc.value.errors == ["value not an allowed option: phq9_3"]
    assert exc.value.safety.show is True and exc.value.safety.resources
    assert db.query(SafetyEvent).count() == 1


def _set_consent(db, uid: str, scope: str, granted: bool | None) -> None:
    row = db.scalars(select(Consent).where(Consent.user_id == uid, Consent.scope == scope)).one()
    if granted is None:
        db.delete(row)
    else:
        row.granted = granted
    db.commit()


# --------------------------------------------------------------------------- consent


@pytest.mark.parametrize("state", [False, None])  # revoked, or never recorded
def test_survey_without_answers_consent_keeps_no_answers(db, state) -> None:
    _set_consent(db, "u1", "survey_answers", state)
    answers = _phq9(1, rest=2)
    out = submit_response(db, "u1", _resp("u1", "phq9", answers))
    assert out["stored"] is True and out["safety"]["show"] is True
    row = db.get(SurveyResponseRow, out["id"])
    assert row.answers is None
    assert row.total == 17
    assert row.scores["band"] == "moderately severe"
    assert len(row.answers_hmac) == 64 and row.answers_hmac == surveys.answers_digest(answers)
    assert "answers_hmac" not in row.scores
    raw = db.execute(
        text("SELECT answers_enc FROM survey_responses WHERE id = :id"), {"id": out["id"]}
    ).scalar_one()
    assert raw is None
    assert "items" not in row.scores
    # safety event still written
    assert db.query(SafetyEvent).count() == 1


def test_answers_digest_is_keyed_and_stable() -> None:
    import hashlib

    a = {"phq2_1": 1, "phq2_2": 0}
    d = surveys.answers_digest(a)
    assert d == surveys.answers_digest(dict(reversed(list(a.items()))))
    assert d != surveys.answers_digest({"phq2_1": 0, "phq2_2": 1})
    plain = hashlib.sha256(b'{"phq2_1":1,"phq2_2":0}').hexdigest()
    assert d != plain


def test_checkin_goes_to_checkins_daily_and_upserts(db) -> None:
    when = _at(2026, 11, 10, 21)
    out1 = submit_response(
        db, "u1", _resp("u1", "daily_pm", {"mood": 1, "stress": 3, "energy": 2}, when=when)
    )
    out2 = submit_response(
        db, "u1", _resp("u1", "daily_pm", {"mood": 3, "stress": 1, "energy": 2}, when=when)
    )
    assert out1["id"] == out2["id"] and out2["stored"] is True
    rows = db.query(CheckinDaily).all()
    assert len(rows) == 1
    r = rows[0]
    assert (r.slot, str(r.date)) == ("pm", "2026-11-10")
    assert r.answers == {"mood": 3, "stress": 1, "energy": 2}
    assert out2["scores"]["items"] == {"mood": 3, "stress": 1, "energy": 2}
    assert db.query(SurveyResponseRow).count() == 0
    submit_response(
        db,
        "u1",
        _resp("u1", "daily_am", {"sleep_quality": 2, "energy": 2, "mood": 2}, when=when),
    )
    assert {r.slot for r in db.query(CheckinDaily).all()} == {"am", "pm"}


@pytest.mark.parametrize("state", [False, None])
def test_checkin_without_consent_stores_nothing(db, state) -> None:
    _set_consent(db, "u1", "checkins", state)
    out = submit_response(
        db, "u1", _resp("u1", "daily_am", {"sleep_quality": 1, "energy": 0, "mood": 0})
    )
    assert out["id"] is None and out["stored"] is False
    assert out["scores"]["items"] == {"sleep_quality": 1, "energy": 0, "mood": 0}
    assert db.query(CheckinDaily).count() == 0
    assert db.query(SurveyResponseRow).count() == 0


# --------------------------------------------------------------------------- weekly indices


def _who5(v: int) -> dict[str, int]:
    return {f"who5_{i}": v for i in range(1, 6)}


WEEK = date(2026, 11, 9)  # a Monday


def test_weekly_indices_latest_score_band_and_item_means(db) -> None:
    submit_response(db, "u1", _resp("u1", "who5", _who5(2), when=_at(2026, 11, 9)))
    submit_response(db, "u1", _resp("u1", "who5", _who5(3), when=_at(2026, 11, 12)))
    phq2 = {"phq2_1": 1, "phq2_2": 2}
    submit_response(db, "u1", _resp("u1", "phq2", phq2, when=_at(2026, 11, 10)))
    for day, mood, stress in [(9, 1, 4), (10, 3, 2), (15, 4, 0)]:
        a = {"mood": mood, "stress": stress, "energy": 2}
        submit_response(db, "u1", _resp("u1", "daily_pm", a, when=_at(2026, 11, day, 21)))
    # Outside the window: Sunday 23:59 before, and the next Monday 00:00 (UTC).
    g = {"gad2_1": 3, "gad2_2": 3}
    submit_response(
        db, "u1", _resp("u1", "gad2", g, when=datetime(2026, 11, 8, 23, 59, tzinfo=UTC))
    )
    submit_response(db, "u1", _resp("u1", "gad2", g, when=datetime(2026, 11, 16, tzinfo=UTC)))
    submit_response(
        db,
        "u1",
        _resp("u1", "daily_pm", {"mood": 0, "stress": 4, "energy": 0}, when=_at(2026, 11, 16)),
    )

    idx = surveys.weekly_indices(db, "u1", WEEK)
    assert idx["who5"] == {  # latest: 15 * 4 = 60, above the <=50 cut-off
        "value": 60.0,
        "band": "above screening cutoff",
        "band_alert": False,
        "direction": -1,
    }
    assert idx["phq2"] == {
        "value": 3.0,
        "band": "at or above screening cutoff",
        "band_alert": True,
        "direction": 1,
    }
    assert idx["daily_pm.mood"]["value"] == pytest.approx(8 / 3)
    assert idx["daily_pm.mood"]["direction"] == -1
    assert idx["daily_pm.stress"] == {
        "value": pytest.approx(2.0),
        "band": None,
        "band_alert": False,
        "direction": 1,
    }
    assert "gad2" not in idx


def test_weekly_indices_low_who5_alerts(db) -> None:
    submit_response(db, "u1", _resp("u1", "who5", _who5(2), when=_at(2026, 11, 10)))  # 40
    idx = surveys.weekly_indices(db, "u1", WEEK)
    assert idx["who5"]["band"] == "low wellbeing" and idx["who5"]["band_alert"] is True


def test_weekly_indices_without_answers_consent_still_has_scores(db) -> None:
    _set_consent(db, "u1", "survey_answers", False)
    submit_response(db, "u1", _resp("u1", "phq9", _phq9(0, rest=2), when=_at(2026, 11, 10)))
    idx = surveys.weekly_indices(db, "u1", WEEK)
    assert idx["phq9"]["value"] == 16.0 and idx["phq9"]["band_alert"] is True


def test_weekly_indices_user_isolation(db) -> None:
    """User A cannot read user B's responses or check-ins through weekly_indices."""
    submit_response(db, "userB", _resp("userB", "who5", _who5(5), when=_at(2026, 11, 10)))
    submit_response(
        db,
        "userB",
        _resp(
            "userB",
            "daily_am",
            {"sleep_quality": 0, "energy": 0, "mood": 0},
            when=_at(2026, 11, 10),
        ),
    )
    assert surveys.weekly_indices(db, "userA", WEEK) == {}
    submit_response(db, "userA", _resp("userA", "who5", _who5(1), when=_at(2026, 11, 11)))
    a = surveys.weekly_indices(db, "userA", WEEK)
    b = surveys.weekly_indices(db, "userB", WEEK)
    assert set(a) == {"who5"} and a["who5"]["value"] == 20.0
    assert b["who5"]["value"] == 100.0 and b["daily_am.mood"]["value"] == 0.0


def test_weekly_indices_requires_user_id(db) -> None:
    with pytest.raises(ValueError):
        surveys.weekly_indices(db, "", WEEK)


def test_weekly_indices_never_decrypts_answers(db, monkeypatch) -> None:
    submit_response(db, "u1", _resp("u1", "who5", _who5(3), when=_at(2026, 11, 10)))

    def boom(*a, **k):
        raise AssertionError("weekly_indices must not touch answers")

    monkeypatch.setattr(security, "decrypt", boom)
    db.expire_all()
    assert surveys.weekly_indices(db, "u1", WEEK)["who5"]["value"] == 60.0


def test_answers_hmac_key_derives_from_field_key_not_secret_key(monkeypatch) -> None:
    from cryptography.fernet import Fernet

    from backend.config import get_settings

    a = {"phq2_1": 1, "phq2_2": 0}

    def digest_with(**env: str) -> str:
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()
        surveys._answers_hmac_key.cache_clear()
        return surveys.answers_digest(a)

    try:
        fk1, fk2 = Fernet.generate_key().decode(), Fernet.generate_key().decode()
        base = digest_with(FIELD_KEY=fk1, SECRET_KEY="s" * 40)
        assert digest_with(FIELD_KEY=fk1, SECRET_KEY="t" * 40) == base  # signing key rotation
        assert digest_with(FIELD_KEY=fk2, SECRET_KEY="s" * 40) != base  # data key change
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        surveys._answers_hmac_key.cache_clear()

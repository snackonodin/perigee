"""DB-backed survey functions against the real backend.models (merged from
feat/db-ingest) on an in-memory SQLite engine from backend.db (foreign keys on).

encrypt() comes from feat/accounts later; until then a placeholder bytes encoder
is swapped in through surveys.set_encryptor (NOT real crypto).
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

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


def placeholder_encrypt(b: bytes) -> bytes:
    return b"ENC:" + base64.b64encode(b[::-1])


def placeholder_decrypt(b: bytes) -> bytes:
    assert b.startswith(b"ENC:")
    return base64.b64decode(b[4:])[::-1]


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture()
def db():
    engine = get_engine("sqlite://")
    Base.metadata.create_all(engine)
    surveys.set_encryptor(placeholder_encrypt)
    with Session(engine) as s:
        s.add_all(User(id=u, email=f"{u}@example.test", is_synthetic=True) for u in USERS)
        s.flush()
        for uid in USERS:
            for scope in ("survey_answers", "checkins"):
                s.add(Consent(user_id=uid, scope=scope, granted=True, policy_version="test"))
        s.commit()
        surveys.load_catalog(s)
        yield s
    surveys.set_encryptor(None)
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
    assert json.loads(placeholder_decrypt(row.answers)) == _phq9(0)
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
    import sys

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


def test_answers_encrypted_at_rest(db) -> None:
    out = submit_response(db, "u1", _resp("u1", "phq9", _phq9(0, rest=2)))
    raw = db.execute(
        text("SELECT answers_enc FROM survey_responses WHERE id = :id"), {"id": out["id"]}
    ).scalar_one()
    assert raw.startswith(b"ENC:")
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
    assert row.answers == b""
    assert row.total == 17
    assert row.scores["band"] == "moderately severe"
    assert row.scores["answers_retained"] is False
    assert len(row.scores["answers_hmac"]) == 64
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

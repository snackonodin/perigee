from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, delete, func, inspect, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from backend.models import (
    AuditLog,
    Base,
    CaptureSession,
    Consent,
    HeartEstimateRow,
    Instrument,
    Marker,
    NightFeaturesRow,
    PipelineRun,
    Profile,
    RawFile,
    SurveyResponseRow,
    User,
    scoped,
)

EXPECTED_TABLES = {
    "users", "refresh_tokens", "profiles", "consents", "sessions", "raw_files", "markers",
    "reference_readings", "window_estimates", "heart_estimates", "night_features",
    "baselines", "flags", "pipeline_runs", "audit_log", "instrument_catalog",
    "survey_responses", "checkins_daily", "indices", "safety_events", "guidance_cards",
    "guidance_shown",
}  # fmt: skip

T0 = datetime(2026, 11, 1, 22, 0, tzinfo=UTC)


@pytest.fixture
def schema(engine: Engine) -> Engine:
    Base.metadata.create_all(engine)
    return engine


def _user(db: Session, email: str, synthetic: bool = False) -> User:
    u = User(email=email, password_hash="x", is_synthetic=synthetic)
    db.add(u)
    db.flush()
    return u


def _session(db: Session, user: User, sha: str = "a" * 64) -> CaptureSession:
    s = CaptureSession(
        user_id=user.id, start_utc=T0, end_utc=T0 + timedelta(hours=1),
        raw_path="/tmp/x", raw_sha256=sha,
    )  # fmt: skip
    db.add(s)
    db.flush()
    return s


def test_all_interface_tables_exist(schema: Engine) -> None:
    assert set(inspect(schema).get_table_names()) == EXPECTED_TABLES
    assert "v_real_users" in inspect(schema).get_view_names()


def test_user_owned_tables_have_indexed_cascading_user_id(schema: Engine) -> None:
    insp = inspect(schema)
    owned = [t for t in Base.metadata.sorted_tables if "user_id" in t.c and t.name != "users"]
    assert len(owned) >= 15
    for t in owned:
        if t.name == "audit_log":
            continue  # audit rows outlive the user: SET NULL, tested below
        fks = [
            fk for fk in insp.get_foreign_keys(t.name) if fk["constrained_columns"] == ["user_id"]
        ]
        assert fks and fks[0]["referred_table"] == "users", t.name
        assert fks[0]["options"].get("ondelete") == "CASCADE", t.name
        indexed = {c for ix in insp.get_indexes(t.name) for c in ix["column_names"]}
        assert "user_id" in indexed or t.name == "profiles", t.name


def test_delete_user_cascades(schema: Engine, db: Session) -> None:
    u = _user(db, "a@x")
    s = _session(db, u)
    db.add(Marker(user_id=u.id, session_id=s.id, host_time=T0, label="lights_out"))
    db.commit()
    db.execute(delete(User).where(User.id == u.id))
    db.commit()
    assert db.scalar(select(func.count()).select_from(CaptureSession)) == 0
    assert db.scalar(select(func.count()).select_from(Marker)) == 0


def test_timestamps_roundtrip_as_utc_text(schema: Engine, db: Session) -> None:
    u = _user(db, "a@x")
    plus2 = datetime(2026, 11, 2, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    s = CaptureSession(
        user_id=u.id, start_utc=plus2, end_utc=plus2 + timedelta(hours=1),
        raw_path="p", raw_sha256="b" * 64,
    )  # fmt: skip
    db.add(s)
    db.commit()
    raw = db.execute(text("SELECT start_utc FROM sessions")).scalar()
    assert raw == "2026-11-01T22:00:00.000000Z"
    db.expire_all()
    assert db.get(CaptureSession, s.id).start_utc == T0


def test_naive_datetime_rejected(schema: Engine, db: Session) -> None:
    u = _user(db, "a@x")
    db.add(
        CaptureSession(
            user_id=u.id,
            start_utc=datetime(2026, 1, 1),
            end_utc=T0,
            raw_path="p",
            raw_sha256="c" * 64,
        )
    )
    with pytest.raises(StatementError, match="naive"):
        db.flush()


def test_night_features_source_kind_check(schema: Engine, db: Session) -> None:
    u = _user(db, "a@x")
    db.add(
        NightFeaturesRow(
            user_id=u.id, date=date(2026, 11, 1), source_kind="synthetic", session_ids=["s1"]
        )
    )
    db.flush()
    db.add(NightFeaturesRow(user_id=u.id, date=date(2026, 11, 2), source_kind="bogus"))
    with pytest.raises(IntegrityError, match="CHECK"):
        db.flush()


def test_heart_estimates_must_be_experimental(schema: Engine, db: Session) -> None:
    u = _user(db, "a@x")
    s = _session(db, u)
    db.add(HeartEstimateRow(user_id=u.id, session_id=s.id, t_start=T0, t_end=T0))
    db.flush()
    db.add(
        HeartEstimateRow(user_id=u.id, session_id=s.id, t_start=T0, t_end=T0, experimental=False)
    )
    with pytest.raises(IntegrityError, match="CHECK"):
        db.flush()


def test_survey_answers_stored_as_bytes_in_answers_enc(schema: Engine, db: Session) -> None:
    u = _user(db, "a@x")
    db.add(
        SurveyResponseRow(
            user_id=u.id,
            instrument_id="phq2",
            instrument_version="1",
            administered_at=T0,
            answers={"q1": 3, "q2": 2},
        )
    )
    db.commit()
    cols = {c["name"] for c in inspect(db.get_bind()).get_columns("survey_responses")}
    assert "answers_enc" in cols and "answers" not in cols
    stored = db.execute(text("SELECT answers_enc FROM survey_responses")).scalar()
    # Ciphertext only. The plaintext is JSON, so it contains '{' and '"', which never occur
    # in a base64 Fernet token: a short marker like b"q1" can match by chance (~2%).
    assert isinstance(stored, bytes) and b'{"q1"' not in stored and b'"q1":' not in stored
    assert stored.startswith(b"gAAAAA")  # Fernet token version byte, base64
    db.expire_all()
    assert db.scalars(select(SurveyResponseRow.answers)).one() == {"q1": 3, "q2": 2}


def test_v_real_users_excludes_synthetic(schema: Engine, db: Session) -> None:
    _user(db, "real@x")
    _user(db, "persona@x", synthetic=True)
    db.commit()
    emails = db.execute(text("SELECT email FROM v_real_users")).scalars().all()
    assert emails == ["real@x"]


def test_scoped_user_a_cannot_read_user_b(schema: Engine, db: Session) -> None:
    a, b = _user(db, "a@x"), _user(db, "b@x")
    sa, sb = _session(db, a, "1" * 64), _session(db, b, "2" * 64)
    db.add_all([
        RawFile(user_id=a.id, session_id=sa.id, path="a", sha256="3" * 64, size_bytes=1),
        RawFile(user_id=b.id, session_id=sb.id, path="b", sha256="4" * 64, size_bytes=1),
    ])  # fmt: skip
    db.commit()
    for model in (CaptureSession, RawFile):
        rows = db.scalars(scoped(select(model), model, a.id)).all()
        assert rows and all(r.user_id == a.id for r in rows)
    assert db.get(CaptureSession, sb.id) is not None  # B's data still exists, just not visible


def test_scoped_rejects_global_models_and_blank_user() -> None:
    with pytest.raises(TypeError):
        scoped(select(Instrument), Instrument, "u")
    # pipeline_runs has a nullable user_id (0003), so job reads can be scoped.
    assert "pipeline_runs.user_id" in str(scoped(select(PipelineRun), PipelineRun, "u"))
    with pytest.raises(ValueError):
        scoped(select(RawFile), RawFile, "")


def test_user_repr_hides_password_hash() -> None:
    assert "x-secret" not in repr(User(email="a@x", password_hash="x-secret"))


def test_audit_log_survives_user_delete(schema: Engine, db: Session) -> None:
    u = _user(db, "a@x")
    db.add(AuditLog(user_id=u.id, action="login"))
    db.commit()
    db.execute(delete(User).where(User.id == u.id))
    db.commit()
    db.expire_all()
    row = db.scalars(select(AuditLog)).one()
    assert row.user_id is None and row.action == "login"


def test_consents_one_row_per_scope(schema: Engine, db: Session) -> None:
    u = _user(db, "a@x")
    db.add(Consent(user_id=u.id, scope="csi_capture", granted=True, policy_version="1"))
    db.flush()
    db.add(Consent(user_id=u.id, scope="csi_capture", granted=False, policy_version="2"))
    with pytest.raises(IntegrityError, match="UNIQUE"):
        db.flush()


def test_profile_display_name_stored_as_bytes(schema: Engine, db: Session) -> None:
    u = _user(db, "a@x")
    db.add(Profile(user_id=u.id, display_name="Ada"))
    db.commit()
    cols = {c["name"] for c in inspect(db.get_bind()).get_columns("profiles")}
    assert "display_name_enc" in cols and "display_name" not in cols
    stored = db.execute(text("SELECT display_name_enc FROM profiles")).scalar()
    # Ciphertext only: JSON '"Ada"' has quotes, which base64 never contains (no chance match)
    assert isinstance(stored, bytes) and b'"Ada"' not in stored
    assert stored.startswith(b"gAAAAA")
    db.expire_all()
    assert db.scalars(select(Profile.display_name)).one() == "Ada"


@pytest.mark.parametrize("bad", ["../etc", "not-a-uuid", "A" * 36, ""])
def test_session_id_must_be_uuid(bad: str) -> None:
    with pytest.raises(ValueError):
        CaptureSession(id=bad)


def test_safety_event_details_encrypted(schema: Engine, db: Session) -> None:
    from backend.models import SafetyEvent

    u = _user(db, "a@x")
    db.add(
        SafetyEvent(
            user_id=u.id, source="phq9", reason="safety_item", details_enc={"item": "phq9_9"}
        )
    )
    db.add(SafetyEvent(user_id=u.id, source="phq9", reason="safety_item"))
    db.commit()
    stored = db.execute(text("SELECT details_enc FROM safety_events")).scalars().all()
    assert None in stored
    blob = next(x for x in stored if x is not None)
    assert isinstance(blob, bytes) and b"phq9_9" not in blob
    db.expire_all()
    assert {"item": "phq9_9"} in db.scalars(select(SafetyEvent.details_enc)).all()

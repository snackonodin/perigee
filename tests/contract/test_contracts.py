"""Contract tests: the shared models reject malformed records (PDF section 11)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from backend.schemas.contracts import (
    HeartEstimate,
    NightFeatures,
    ReferenceReading,
    RunRecord,
    SessionRecord,
    SurveyResponse,
    WindowEstimate,
)
from csi_core.config import get_config

T0 = datetime(2026, 11, 10, 22, 0, tzinfo=UTC)


def test_config_loads() -> None:
    cfg = get_config()
    assert cfg.capture.timestamp_bits == 32
    assert cfg.preprocess.breath_band_hz[0] < cfg.preprocess.breath_band_hz[1]


def test_session_valid() -> None:
    s = SessionRecord(user_id="u1", start_utc=T0, end_utc=T0 + timedelta(hours=8))
    assert len(s.id) == 36 and s.usable is False


def test_session_rejects_naive_time() -> None:
    with pytest.raises(ValidationError):
        SessionRecord(user_id="u1", start_utc=datetime(2026, 1, 1), end_utc=T0)


def test_session_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError):
        SessionRecord(user_id="u1", start_utc=T0, end_utc=T0 - timedelta(seconds=1))


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        SessionRecord(user_id="u1", start_utc=T0, end_utc=T0 + timedelta(1), colour="red")


def test_window_rejects_bad_rr_and_quality() -> None:
    kw = dict(session_id="s", t_start=T0, t_end=T0 + timedelta(seconds=60))
    WindowEstimate(**kw, rr_a=14.5, quality=0.9)
    with pytest.raises(ValidationError):
        WindowEstimate(**kw, rr_a=-1)
    with pytest.raises(ValidationError):
        WindowEstimate(**kw, quality=1.5)


def test_heart_must_stay_experimental() -> None:
    with pytest.raises(ValidationError):
        HeartEstimate(session_id="s", t_start=T0, t_end=T0 + timedelta(60), experimental=False)


def test_reference_plausibility() -> None:
    ReferenceReading(session_id="s", ts=T0, kind="spo2", value=97, source="oximeter")
    with pytest.raises(ValidationError):
        ReferenceReading(session_id="s", ts=T0, kind="spo2", value=140, source="oximeter")


def test_night_bounds() -> None:
    NightFeatures(user_id="u", date=date(2026, 11, 10), presence_hours=7.5)
    with pytest.raises(ValidationError):
        NightFeatures(user_id="u", date=date(2026, 11, 10), presence_hours=25)


def test_survey_answers_redacted_in_repr() -> None:
    r = SurveyResponse(
        user_id="u", instrument_id="phq2", instrument_version="1",
        administered_at=T0, answers={"q1": 3, "q2": 2},
    )
    assert "3" not in repr(r).split("answers=")[1]
    with pytest.raises(ValidationError):
        SurveyResponse(user_id="u", instrument_id="phq2", instrument_version="1",
                       administered_at=T0, answers={})


def test_run_record_hash_format() -> None:
    RunRecord(kind="process_session", code_version="abc123", input_hashes=["a" * 64])
    with pytest.raises(ValidationError):
        RunRecord(kind="process_session", code_version="abc123", input_hashes=["nothex"])

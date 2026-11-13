"""Station time replaces Earth time zones: an optional offset from UTC (user, 2026-11-14)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from backend.services import accounts as acc
from backend.services import pipeline
from backend.services import station_time as st
from tests.api.conftest import data_dir, db, engine  # noqa: F401  (fixtures)

PW = "long enough password"


def test_blank_station_time_means_utc(db) -> None:  # noqa: F811
    r = acc.signup(db, "a@b.co", PW)
    assert acc.get_me(db, r.user_id)["station_time_offset_min"] is None
    assert pipeline.user_tz(db, r.user_id) is UTC


def test_station_offset_moves_night_boundaries(db) -> None:  # noqa: F811
    r = acc.signup(db, "a@b.co", PW)
    me = acc.update_profile(db, r.user_id, {"station_time_offset_min": 330})
    assert me["station_time_offset_min"] == 330
    tz = pipeline.user_tz(db, r.user_id)
    assert tz.utcoffset(None) == timedelta(minutes=330)
    utc_a, utc_b = pipeline.night_bounds_utc(date(2026, 11, 10), UTC)
    a, b = pipeline.night_bounds_utc(date(2026, 11, 10), tz)
    assert a == utc_a - timedelta(minutes=330) and b - a == timedelta(hours=24)
    # 23:00 station time on the 10th belongs to the night of the 10th
    ts = datetime(2026, 11, 10, 23, 0, tzinfo=tz).astimezone(UTC)
    assert pipeline.night_date(ts, tz) == date(2026, 11, 10)


def test_clearing_station_time_returns_to_utc(db) -> None:  # noqa: F811
    r = acc.signup(db, "a@b.co", PW)
    acc.update_profile(db, r.user_id, {"station_time_offset_min": -240})
    me = acc.update_profile(db, r.user_id, {"station_time_offset_min": None})
    assert me["station_time_offset_min"] is None
    assert pipeline.user_tz(db, r.user_id) is UTC


@pytest.mark.parametrize("bad", [-721, 841, 1.5, "330", True])
def test_out_of_range_or_non_integer_is_rejected(db, bad) -> None:  # noqa: F811
    r = acc.signup(db, "a@b.co", PW)
    with pytest.raises(acc.InvalidInput):
        acc.update_profile(db, r.user_id, {"station_time_offset_min": bad})


def test_legacy_timezone_no_longer_moves_nights(db) -> None:  # noqa: F811
    r = acc.signup(db, "a@b.co", PW)
    acc.update_profile(db, r.user_id, {"timezone": "America/New_York"})
    assert pipeline.user_tz(db, r.user_id) is UTC


def test_station_time_is_per_user(db) -> None:  # noqa: F811
    a = acc.signup(db, "a@b.co", PW)
    b = acc.signup(db, "b@b.co", PW)
    acc.update_profile(db, a.user_id, {"station_time_offset_min": 120})
    assert pipeline.user_tz(db, b.user_id) is UTC
    assert acc.get_me(db, b.user_id)["station_time_offset_min"] is None


def test_tz_label_is_not_an_earth_zone() -> None:
    assert st.tz_for_offset(330).tzname(None) == "Station UTC+05:30"
    assert st.tz_for_offset(-90).tzname(None) == "Station UTC-01:30"
    assert st.tz_for_offset(None) is UTC and st.tz_for_offset(0) is UTC

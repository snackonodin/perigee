"""LEAK-1b (lesson L6): a backfilled night never sees answers given after it.

run_nightly passes until=<night end (next local noon)> to weekly_indices, so a
survey answered on Wednesday cannot raise a flag on Monday's night of the same week,
even when Monday is processed later (backfill).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from backend.models import Flag
from backend.schemas.contracts import SurveyResponse
from backend.services import fusion, surveys
from backend.services.injection import inject

from .conftest import make_user

MONDAY, WEDNESDAY = date(2026, 11, 9), date(2026, 11, 11)


def _night(db, uid: str, day: date) -> None:
    onset = datetime(day.year, day.month, day.day, 23, tzinfo=UTC)
    ws = [
        {
            "t_start": (onset + timedelta(seconds=30 * k)).isoformat(),
            "t_end": (onset + timedelta(seconds=30 * k + 60)).isoformat(),
            "rr_a": 14.0,
            "rr_b": 14.0,
            "pnr_db": 9.0,
            "quality": 0.9,
        }
        for k in range(int(7 * 3600 / 30))
    ]
    inject(
        db,
        uid,
        {"session": {"start_utc": ws[0]["t_start"], "end_utc": ws[-1]["t_end"]}, "windows": ws},
        "test",
    )


def test_backfilled_night_does_not_see_later_answers(db, data_dir) -> None:
    uid = make_user(db)
    surveys.load_catalog(db)
    _night(db, uid, MONDAY)
    _night(db, uid, WEDNESDAY)
    inst = surveys.get_instrument(db, "phq2")
    surveys.submit_response(
        db,
        uid,
        SurveyResponse(  # alert band, answered Wednesday noon
            user_id=uid,
            instrument_id="phq2",
            instrument_version=inst["version"],
            administered_at=datetime(2026, 11, 11, 12, tzinfo=UTC),
            answers={"phq2_1": 2, "phq2_2": 1},
        ),
    )

    mon = fusion.run_nightly(db, uid, MONDAY)  # backfill: the answer is already stored
    db.commit()
    assert mon["flags"] == 0
    wed = fusion.run_nightly(db, uid, WEDNESDAY)
    db.commit()
    assert wed["states"] == ["mental_only"]
    flags = db.scalars(select(Flag).where(Flag.user_id == uid)).all()
    assert [f.date for f in flags] == [WEDNESDAY]
    assert flags[0].components["mental"]["phq2"]["band"]["band"] == "at or above screening cutoff"


def test_until_is_the_night_end(db, data_dir) -> None:
    uid = make_user(db)
    _night(db, uid, MONDAY)
    seen = []

    def provider(_db, _uid, week, *, until=None):
        seen.append(until)
        return {}

    fusion.run_nightly(db, uid, MONDAY, indices_provider=provider)
    assert seen and all(u == datetime(2026, 11, 10, 12, tzinfo=UTC) for u in seen)

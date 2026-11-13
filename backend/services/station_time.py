"""Station time: the clock the crew lives by, as an optional offset from UTC.

Astronauts do not live in Earth time zones. A station keeps a reference clock (the ISS keeps
UTC, the time scale kept by atomic clocks). The person may optionally enter their station's
clock time once; the app stores only the offset from UTC in minutes
(``profiles.settings["station_time_offset_min"]``). Blank means UTC.

Night boundaries (which night a sleep session belongs to) use this offset. The legacy
``profiles.timezone`` column is no longer read.
"""

from __future__ import annotations

from datetime import UTC, timedelta, timezone, tzinfo
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Profile, scoped

SETTINGS_KEY = "station_time_offset_min"
MIN_OFFSET, MAX_OFFSET = -12 * 60, 14 * 60  # widest offsets any reference clock uses


def validate_offset(value: Any) -> int | None:
    """None clears the setting (UTC). Otherwise an int in [-720, 840] minutes."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("station_time_offset_min must be an integer number of minutes or null")
    if not MIN_OFFSET <= value <= MAX_OFFSET:
        raise ValueError("station_time_offset_min must be between -720 and 840")
    return value


def offset_from_settings(settings: dict[str, Any] | None) -> int | None:
    try:
        return validate_offset((settings or {}).get(SETTINGS_KEY))
    except ValueError:
        return None


def tz_for_offset(offset_min: int | None) -> tzinfo:
    if not offset_min:
        return UTC
    sign = "+" if offset_min > 0 else "-"
    h, m = divmod(abs(offset_min), 60)
    return timezone(timedelta(minutes=offset_min), f"Station UTC{sign}{h:02d}:{m:02d}")


def station_tz(db: Session, user_id: str) -> tzinfo:
    settings = db.scalar(scoped(select(Profile.settings), Profile, user_id))
    return tz_for_offset(offset_from_settings(settings))

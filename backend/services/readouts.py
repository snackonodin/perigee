"""Read views for the API: nights, flags, indices, check-ins and /today.

Every query goes through scoped(model, user_id). Every score carries its inputs
and run_id (plan section 20: provenance). Heart rate is never exposed (FR8: it
stays experimental and the demo cut its display). "Today" is the UTC date.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import (
    Baseline,
    CheckinDaily,
    ContextEngineNight,
    Flag,
    NightFeaturesRow,
    scoped,
)
from backend.services import guidance, hazards, surveys

DEFAULT_RANGE_DAYS = 14
MAX_RANGE_DAYS = 366
TODAY_FLAG_DAYS = 7
TODAY_MAX_FLAGS = 3
CHECKIN_INSTRUMENTS = {"am": "daily_am", "pm": "daily_pm"}


class InvalidRange(ValueError):
    pass


def utc_today() -> date:
    return datetime.now(UTC).date()


def resolve_range(start: date | None, end: date | None) -> tuple[date, date]:
    """Inclusive [start, end]; defaults to the last DEFAULT_RANGE_DAYS days ending today."""
    end = end or utc_today()
    start = start or end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if start > end:
        raise InvalidRange("from must be on or before to")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise InvalidRange(f"range is limited to {MAX_RANGE_DAYS} days")
    return start, end


def week_start(day: date | None) -> date:
    day = day or utc_today()
    return day - timedelta(days=day.weekday())  # ISO week: Monday


# --------------------------------------------------------------------------- serializers


def night_dict(n: NightFeaturesRow) -> dict[str, Any]:
    return {
        "id": n.id,
        "date": n.date,
        "rr_med": n.rr_med,
        "rr_var": n.rr_var,
        "presence_hours": n.presence_hours,
        "restless_frac": n.restless_frac,
        "onset": n.onset,
        "wake": n.wake,
        "midsleep": n.midsleep,
        "quality": n.quality,
        "valid": n.valid,
        "source_kind": n.source_kind,
        "inputs": {"session_ids": list(n.session_ids or [])},
        "run_id": n.run_id,
    }


def flag_dict(f: Flag) -> dict[str, Any]:
    return {
        "id": f.id,
        "date": f.date,
        "domain_pair": f.domain_pair,
        "phys_level": f.phys_level,
        "mental_level": f.mental_level,
        "state": f.state,
        "priority": f.priority,
        "message_key": f.message_key,
        "components": f.components or {},  # the "why": values, baselines, z, bands
        "run_id": f.run_id,
        "created_at": f.created_at,
    }


def checkin_dict(c: CheckinDaily) -> dict[str, Any]:
    return {
        "id": c.id,
        "date": c.date,
        "slot": c.slot,
        "instrument_id": c.instrument_id,
        "instrument_version": c.instrument_version,
        "answers": c.answers,  # amber class, the user's own data
        "tags": list(c.tags or []),
        "created_at": c.created_at,
    }


def baseline_dict(b: Baseline) -> dict[str, Any]:
    return {
        "feature": b.feature,
        "maturity": b.maturity,
        "n": b.n,
        "median": b.median,
        "mad": b.mad,
        "window_days": b.window_days,
        "updated_at": b.updated_at,
    }


# --------------------------------------------------------------------------- reads


def list_nights(db: Session, user_id: str, start: date, end: date) -> list[dict]:
    stmt = scoped(
        select(NightFeaturesRow)
        .where(NightFeaturesRow.date >= start, NightFeaturesRow.date <= end)
        .order_by(NightFeaturesRow.date.desc(), NightFeaturesRow.source_kind),
        NightFeaturesRow,
        user_id,
    )
    return [night_dict(n) for n in db.scalars(stmt)]


def nights_on(db: Session, user_id: str, day: date) -> list[dict]:
    """All rows for one night (one per source_kind)."""
    return list_nights(db, user_id, day, day)


def list_flags(db: Session, user_id: str, since: date) -> list[dict]:
    stmt = scoped(
        select(Flag).where(Flag.date >= since).order_by(Flag.date.desc(), Flag.priority.desc()),
        Flag,
        user_id,
    )
    return [flag_dict(f) for f in db.scalars(stmt)]


def list_checkins(db: Session, user_id: str, start: date, end: date) -> list[dict]:
    stmt = scoped(
        select(CheckinDaily)
        .where(CheckinDaily.date >= start, CheckinDaily.date <= end)
        .order_by(CheckinDaily.date.desc(), CheckinDaily.slot),
        CheckinDaily,
        user_id,
    )
    return [checkin_dict(c) for c in db.scalars(stmt)]


def indices_for_week(db: Session, user_id: str, day: date | None) -> dict[str, Any]:
    ws = week_start(day)
    return {
        "week_start": ws,
        "indices": surveys.weekly_indices(db, user_id, ws),
        "run_id": None,  # computed on request from stored scores; no pipeline run
    }


def today(db: Session, user_id: str, on: date | None = None) -> dict[str, Any]:
    """The /today view. Showing flags records guidance_shown (via select_guidance)."""
    on = on or utc_today()

    latest = db.scalars(
        scoped(
            select(NightFeaturesRow)
            .where(NightFeaturesRow.date <= on)
            .order_by(NightFeaturesRow.date.desc(), NightFeaturesRow.source_kind)
            .limit(1),
            NightFeaturesRow,
            user_id,
        )
    ).first()

    since = on - timedelta(days=TODAY_FLAG_DAYS - 1)
    top = db.scalars(
        scoped(
            select(Flag)
            .where(Flag.date >= since, Flag.date <= on)
            .order_by(Flag.priority.desc(), Flag.date.desc())
            .limit(TODAY_MAX_FLAGS),
            Flag,
            user_id,
        )
    ).all()
    flags = [flag_dict(f) | {"guidance": guidance.select_guidance(db, user_id, f.id)} for f in top]

    answered = set(
        db.scalars(
            scoped(
                select(CheckinDaily.slot).where(CheckinDaily.date == on),
                CheckinDaily,
                user_id,
            )
        )
    )
    consent = surveys.has_consent(db, user_id, surveys.CONSENT_CHECKINS)
    pending = []
    for slot, inst_id in CHECKIN_INSTRUMENTS.items():
        if slot in answered:
            continue
        try:
            version = surveys.get_instrument(db, inst_id)["version"]
        except surveys.UnknownInstrument:
            version = None
        pending.append({"slot": slot, "instrument_id": inst_id, "instrument_version": version})

    baselines = db.scalars(
        scoped(select(Baseline).order_by(Baseline.feature), Baseline, user_id)
    ).all()

    engine_night = db.scalar(
        scoped(
            select(ContextEngineNight)
            .where(ContextEngineNight.date <= on)
            .order_by(ContextEngineNight.date.desc())
            .limit(1),
            ContextEngineNight,
            user_id,
        )
    )

    return {
        "date": on,
        "latest_night": night_dict(latest) if latest else None,
        "flags": flags,
        "pending_checkins": pending,
        "checkins_consent": consent,  # without it, answered check-ins are not stored
        "baselines": [baseline_dict(b) for b in baselines],
        "context_engine": engine_night.output_json if engine_night else None,
        "sync_status": {"state": "offline"},
        **hazards.today_context(db, user_id),
        **surveys.safety_state(db, user_id),
    }

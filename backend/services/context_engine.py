"""Backend adapter for the Context Engine; all scoring stays in engine.api.run."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import (
    Baseline,
    CheckinDaily,
    ContextEngineNight,
    Profile,
    SurveyResponseRow,
    scoped,
)
from backend.services.pipeline import night_bounds_utc
from csi_core.config import ROOT

STATE_SCHEMA_VERSION = "1"


def engine_revision() -> str:
    """Return the checked-out code revision, or a source hash in an archive."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=5,
        )
        if result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    # Hash the engine file actually imported (waiwai1/engine locally, deploy/vendor/engine in a
    # deployment), so the revision is recorded even where there is no git checkout.
    try:
        from engine import api as engine_api
    except ModuleNotFoundError:
        from waiwai1.engine import api as engine_api
    return hashlib.sha256(Path(engine_api.__file__).read_bytes()).hexdigest()


def _prior(db: Session, user_id: str, day: date) -> ContextEngineNight | None:
    return db.scalar(
        scoped(
            select(ContextEngineNight)
            .where(ContextEngineNight.date < day)
            .order_by(ContextEngineNight.date.desc())
            .limit(1),
            ContextEngineNight,
            user_id,
        )
    )


def _checkins(db: Session, user_id: str, day: date, until: datetime) -> dict[str, Any]:
    rows = db.scalars(
        scoped(
            select(CheckinDaily)
            .where(CheckinDaily.date <= day)
            .order_by(CheckinDaily.date.desc(), CheckinDaily.slot),
            CheckinDaily,
            user_id,
        )
    ).all()
    out: dict[str, Any] = {}
    accepted = {
        "stress", "stress_vas", "workload", "evening_workload", "fatigue", "fatigue_vas",
        "morning_kss", "mood_vas", "late_caffeine", "somatic_score",
    }
    aliases = {"stress": "evening_stress", "workload": "evening_workload", "fatigue": "fatigue_vas"}
    for row in rows:
        # Only the most recent value for a field is used; raw answers are never logged.
        if row.date > day:
            continue
        for key, value in (row.answers or {}).items():
            if key in accepted:
                out.setdefault(aliases.get(key, key), value)
    return out


def _clinical(db: Session, user_id: str, until: datetime) -> dict[str, Any]:
    stmt = scoped(
        select(SurveyResponseRow)
        .where(SurveyResponseRow.instrument_id.in_(("phq9", "gad7", "who5", "k6")))
        .where(SurveyResponseRow.administered_at < until)
        .order_by(SurveyResponseRow.administered_at.desc()),
        SurveyResponseRow,
        user_id,
    )
    latest: dict[str, SurveyResponseRow] = {}
    for row in db.scalars(stmt):
        latest.setdefault(row.instrument_id, row)
    clinical: dict[str, Any] = {}
    for instrument, row in latest.items():
        score = (row.scores or {}).get("score")
        if score is not None:
            clinical[instrument] = score
        if instrument == "phq9" and isinstance(row.answers, dict):
            item9 = row.answers.get("phq9_9", row.answers.get("phq9_item9"))
            if item9 is not None:
                clinical["phq9_item9"] = item9
    return clinical


def build_payload(
    db: Session, user_id: str, day: date, night: Any
) -> tuple[dict[str, Any], ContextEngineNight | None]:
    """Assemble the engine's documented JSON input from stored, user-scoped data."""
    until = night_bounds_utc(day, _timezone(db, user_id))[1]
    base = db.scalar(
        scoped(select(Baseline).where(Baseline.feature == "rr_med"), Baseline, user_id)
    )
    profile = db.scalar(scoped(select(Profile), Profile, user_id))
    state_row = _prior(db, user_id, day)
    state = dict(state_row.state_json) if state_row else {}
    if state:
        state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    payload: dict[str, Any] = {
        "mode": "DAILY_NIGHTLY_PROCESS",
        "persona": {
            "user_id": user_id,
            "traits": (profile.settings or {}).get("traits", {}) if profile else {},
            "baselines": {
                "rr_med": base.median if base and base.median is not None else night.rr_med or 0.0,
                "mad_rr": base.mad if base and base.mad is not None else 0.40,
            },
        },
        "sensing_data": {
            "rr_med": night.rr_med or 0.0,
            "rr_var": night.rr_var or 0.0,
            "restless_frac": night.restless_frac,
            "midsleep_shift": 0.0,
            "quality": night.quality,
            "valid_hours": night.presence_hours,
        },
        "behavioral_inputs": _checkins(db, user_id, day, until),
        "clinical_scales": _clinical(db, user_id, until),
        "cognitive_results": {},
        "environmental_logs": {},
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
    if state:
        payload["state"] = state
    return payload, state_row


def run_night(
    db: Session, user_id: str, day: date, night: Any, run_id: str | None
) -> dict[str, Any]:
    """Call the single engine entry point and idempotently persist non-crisis output."""
    try:
        from engine.api import run
    except ModuleNotFoundError as exc:
        if exc.name != "engine":
            raise
        from waiwai1.engine.api import run

    payload, _ = build_payload(db, user_id, day, night)
    output = run(payload)
    if output.get("safety_status", {}).get("crisis_override_triggered"):
        return output
    state = dict(output.get("state") or {})
    state["schema_version"] = STATE_SCHEMA_VERSION
    output["state"] = state
    existing = db.scalar(
        scoped(
            select(ContextEngineNight).where(ContextEngineNight.date == day),
            ContextEngineNight,
            user_id,
        )
    )
    if existing is None:
        existing = ContextEngineNight(user_id=user_id, date=day)
        db.add(existing)
    existing.output_json = output
    existing.state_json = state
    existing.engine_revision = engine_revision()
    existing.run_id = run_id
    db.flush()
    return output


def _timezone(db: Session, user_id: str):
    from backend.services.station_time import station_tz

    return station_tz(db, user_id)

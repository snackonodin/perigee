"""run_nightly: windows -> night_features -> baselines -> flags (FR7, FR9, FR13).

Registered as run kind "run_nightly" with params {"user_id", "day"} (ISO date,
the local evening date of the night). Order per night:

1. Aggregate the night's windows (local noon to noon, profile timezone) and upsert
   night_features on (user_id, date, source_kind).
2. Build each baseline from earlier nights only: valid, inside baseline.window_days,
   and with no flag on that date (FR13: "alert" = a flag exists for that night).
3. Score the night against those baselines plus the latest weekly indices, and
   upsert flags on (user_id, date, domain_pair); stale drafts for the date go.
4. Store baselines that also include tonight when it is valid and not flagged.

Every row written carries run_id. Re-running a night replaces, never appends.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.models import (
    Baseline,
    CaptureSession,
    Flag,
    IndexValue,
    NightFeaturesRow,
    PipelineRun,
    WindowEstimateRow,
    scoped,
)
from backend.schemas.contracts import BaselineState, NightFeatures, SourceKind, WindowEstimate
from backend.services.pipeline import night_bounds_utc, user_tz
from csi_core import night as night_mod
from csi_core.config import CoreConfig, get_config
from csi_core.fusion import PHYS_FEATURES, score_night

# indices_provider(db, user_id, week_start) -> {name: {"value", "band",
# "band_alert", "direction"}} (surveys.weekly_indices). A bare float is accepted
# and treated as having no direction (skipped by score_night).
IndicesProvider = Callable[[Session, str, date], Mapping[str, Any]]


def week_start(day: date) -> date:
    """Monday of the week containing ``day``."""
    return day - timedelta(days=day.weekday())


def _default_indices(db: Session, user_id: str, week: date) -> Mapping[str, Any]:
    try:
        from backend.services.surveys import weekly_indices  # lazy: feat/surveys
    except ImportError:
        return {}
    return weekly_indices(db, user_id, week)


def latest_indices(
    db: Session, user_id: str, day: date, provider: IndicesProvider, cfg: CoreConfig
) -> dict[str, tuple[date, Mapping[str, Any] | float]]:
    """Per index, its most recent week (Monday <= day), looking back at most
    baseline.window_days. A weekly survey keeps its latest band even when the
    current week only has daily check-ins. Returns {name: (week_start, entry)}."""
    week = week_start(day)
    out: dict[str, tuple[date, Mapping[str, Any] | float]] = {}
    for k in range(max(cfg.baseline.window_days // 7, 1)):
        w = week - timedelta(weeks=k)
        for name, entry in (provider(db, user_id, w) or {}).items():
            out.setdefault(name, (w, entry))
    return out


def _split_indices(raw: Mapping[str, Any]) -> tuple[dict, dict, dict]:
    values: dict[str, float] = {}
    direction: dict[str, int] = {}
    bands: dict[str, str] = {}
    for name, v in raw.items():
        if isinstance(v, Mapping):
            if v.get("value") is not None:
                values[name] = float(v["value"])
            if v.get("direction") in (1, -1):
                direction[name] = int(v["direction"])
            if v.get("band_alert") and v.get("band"):
                bands[name] = str(v["band"])
        elif v is not None:
            values[name] = float(v)
    return values, direction, bands


def _night_windows(db: Session, user_id: str, day: date) -> list[WindowEstimate]:
    a, b = night_bounds_utc(day, user_tz(db, user_id))
    stmt = scoped(
        select(WindowEstimateRow).where(
            WindowEstimateRow.t_start >= a, WindowEstimateRow.t_start < b
        ),
        WindowEstimateRow,
        user_id,
    ).order_by(WindowEstimateRow.t_start)
    return [
        WindowEstimate(
            session_id=r.session_id,
            t_start=r.t_start,
            t_end=r.t_end,
            rr_a=r.rr_a,
            rr_b=r.rr_b,
            pnr_db=r.pnr_db,
            motion_flag=r.motion_flag,
            quality=r.quality,
            presence=r.presence,
            run_id=r.run_id,
        )
        for r in db.scalars(stmt)
    ]


def _source_kind(db: Session, user_id: str, session_ids: list[str]) -> str:
    stmt = scoped(
        select(CaptureSession.source_kind).where(CaptureSession.id.in_(session_ids)),
        CaptureSession,
        user_id,
    )
    kinds = set(db.scalars(stmt))
    # Any synthetic input makes the night synthetic: keeps it out of real statistics.
    return SourceKind.synthetic.value if SourceKind.synthetic.value in kinds else "csi"


def _upsert_night(db: Session, nf: NightFeatures, run_id: str | None) -> NightFeaturesRow:
    stmt = scoped(
        select(NightFeaturesRow).where(
            NightFeaturesRow.date == nf.date, NightFeaturesRow.source_kind == nf.source_kind
        ),
        NightFeaturesRow,
        nf.user_id,
    )
    row = db.scalar(stmt)
    data = nf.model_dump(exclude={"run_id"}, mode="python")
    data["source_kind"] = nf.source_kind.value
    if row is None:
        row = NightFeaturesRow(**data)
        db.add(row)
    else:
        for k, v in data.items():
            setattr(row, k, v)
    row.run_id = run_id
    return row


def _flagged_dates(db: Session, user_id: str, a: date, b: date) -> set[date]:
    stmt = scoped(select(Flag.date).where(Flag.date >= a, Flag.date <= b), Flag, user_id)
    return set(db.scalars(stmt))


def _phys_history(
    db: Session, user_id: str, day: date, source_kind: str, cfg: CoreConfig, include_day: bool
) -> dict[str, list[float]]:
    """Per-feature values from valid, non-flagged nights in the baseline window."""
    lo = day - timedelta(days=cfg.baseline.window_days - 1)
    hi = day if include_day else day - timedelta(days=1)
    stmt = scoped(
        select(NightFeaturesRow).where(
            NightFeaturesRow.date >= lo,
            NightFeaturesRow.date <= hi,
            NightFeaturesRow.valid.is_(True),
            NightFeaturesRow.source_kind == source_kind,
        ),
        NightFeaturesRow,
        user_id,
    ).order_by(NightFeaturesRow.date)
    flagged = _flagged_dates(db, user_id, lo, hi)
    hist: dict[str, list[float]] = {f: [] for f in PHYS_FEATURES}
    for r in db.scalars(stmt):
        if r.date in flagged:
            continue
        for f in PHYS_FEATURES:
            v = getattr(r, f)
            if v is not None:
                hist[f].append(float(v))
    return hist


def _store_indices(db: Session, user_id: str, latest: dict[str, tuple[date, Any]]) -> None:
    """Persist each index's latest weekly value (indices table, FR9). Upsert."""
    for name, (week, entry) in latest.items():
        value = entry.get("value") if isinstance(entry, Mapping) else entry
        if value is None:
            continue
        stmt = scoped(
            select(IndexValue).where(IndexValue.week_start == week, IndexValue.name == name),
            IndexValue,
            user_id,
        )
        row = db.scalar(stmt)
        if row is None:
            row = IndexValue(user_id=user_id, week_start=week, name=name, value=float(value))
            db.add(row)
        row.value = float(value)


def _mental_history(
    db: Session, user_id: str, weeks: dict[str, date], cfg: CoreConfig
) -> dict[str, list[float]]:
    """Per index, values from weeks before its latest week, inside the baseline window."""
    if not weeks:
        return {}
    lo = min(weeks.values()) - timedelta(days=cfg.baseline.window_days)
    stmt = scoped(
        select(IndexValue).where(IndexValue.name.in_(list(weeks)), IndexValue.week_start >= lo),
        IndexValue,
        user_id,
    ).order_by(IndexValue.week_start)
    hist: dict[str, list[float]] = {n: [] for n in weeks}
    for r in db.scalars(stmt):
        top = weeks[r.name]
        if top - timedelta(days=cfg.baseline.window_days) <= r.week_start < top:
            hist[r.name].append(float(r.value))
    return hist


def _baselines(user_id: str, hist: dict[str, list[float]], cfg: CoreConfig) -> dict:
    out = {}
    for feature, values in hist.items():
        prev = BaselineState(user_id=user_id, feature=feature, window_days=cfg.baseline.window_days)
        out[feature] = night_mod.update_baseline(prev, values, cfg)
    return out


def _store_baselines(db: Session, user_id: str, states: dict[str, BaselineState]) -> None:
    for feature, st in states.items():
        row = db.scalar(
            scoped(select(Baseline).where(Baseline.feature == feature), Baseline, user_id)
        )
        if row is None:
            row = Baseline(user_id=user_id, feature=feature, window_days=st.window_days)
            db.add(row)
        row.median, row.mad, row.n = st.median, st.mad, st.n
        row.window_days, row.maturity = st.window_days, st.maturity.value


def _replace_flags(db: Session, user_id: str, day: date, drafts: list, run_id: str | None) -> int:
    existing = {
        f.domain_pair: f
        for f in db.scalars(scoped(select(Flag).where(Flag.date == day), Flag, user_id))
    }
    keep = {d.domain_pair for d in drafts}
    stale = [p for p in existing if p not in keep]
    if stale:
        db.execute(
            scoped(
                delete(Flag).where(Flag.date == day, Flag.domain_pair.in_(stale)), Flag, user_id
            ),
            execution_options={"synchronize_session": "fetch"},
        )
    for d in drafts:
        row = existing.get(d.domain_pair)  # update in place: keeps guidance_shown links
        if row is None:
            row = Flag(user_id=user_id, date=day, domain_pair=d.domain_pair)
            db.add(row)
        row.phys_level, row.mental_level, row.state = d.phys_level, d.mental_level, d.state
        row.priority, row.components, row.message_key = d.priority, d.components, d.message_key
        row.run_id = run_id
    return len(drafts)


def run_nightly(
    db: Session,
    user_id: str,
    day: date,
    *,
    run_id: str | None = None,
    indices_provider: IndicesProvider | None = None,
    cfg: CoreConfig | None = None,
) -> dict:
    """Process one night for one user. Does not commit (runs.execute does)."""
    cfg = cfg or get_config()
    windows = _night_windows(db, user_id, day)
    if not windows:
        return {"night": day.isoformat(), "windows": 0, "flags": 0}

    nf = night_mod.aggregate(user_id, day, windows, cfg)
    nf = nf.model_copy(
        update={
            "source_kind": SourceKind(_source_kind(db, user_id, nf.session_ids)),
            "run_id": run_id,
        }
    )
    _upsert_night(db, nf, run_id)
    db.flush()

    latest = latest_indices(db, user_id, day, indices_provider or _default_indices, cfg)
    values, direction, bands = _split_indices({k: e for k, (_, e) in latest.items()})
    _store_indices(db, user_id, latest)
    db.flush()

    sk = nf.source_kind.value
    prior = _baselines(user_id, _phys_history(db, user_id, day, sk, cfg, include_day=False), cfg)
    mental_prior = _baselines(
        user_id, _mental_history(db, user_id, {k: latest[k][0] for k in values}, cfg), cfg
    )
    drafts = score_night(
        nf,
        prior | mental_prior,
        values,
        cfg,
        index_direction=direction,
        mental_band_alerts=bands,
    )
    n_flags = _replace_flags(db, user_id, day, drafts, run_id)
    db.flush()

    # FR13: tonight joins the stored baseline only if valid and not flagged.
    stored = _baselines(user_id, _phys_history(db, user_id, day, sk, cfg, include_day=True), cfg)
    _store_baselines(db, user_id, stored | mental_prior)
    db.flush()
    return {
        "night": day.isoformat(),
        "windows": len(windows),
        "valid": nf.valid,
        "flags": n_flags,
        "states": [d.state for d in drafts],
    }


def run_nightly_handler(db: Session, run: PipelineRun) -> str:
    p = run.parameters
    day = p.get("day") or p.get("date")  # tools/cli.py sends "date"
    if not p.get("user_id") or not day:
        raise ValueError("run_nightly params must include user_id and day (ISO date)")
    out = run_nightly(db, p["user_id"], date.fromisoformat(day), run_id=run.id)
    return (
        f"run_nightly night={out['night']} windows={out['windows']} "
        f"valid={out.get('valid')} flags={out['flags']}"
    )


RUN_KINDS = {"run_nightly": run_nightly_handler}

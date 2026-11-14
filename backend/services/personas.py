"""Demo personas (docs/ops/personas.md, OPS-6): three synthetic users, end to end.

seed(db, anchor=D) builds, per persona, with every value generated (no real data):
- the user (is_synthetic, profile tz UTC, consents check-ins + survey answers);
- daily check-ins D-14..D-1 and weekly PHQ-2 / GAD-2 / WHO-5 on D-14 and D-7, through
  surveys.submit_response (P3's final PHQ-9 only with include_final_phq9);
- 13 history nights D-14..D-2 as window-level rows (one synthetic session each);
- the demo night D-1 as 6.0 h of window-level rows plus a 1.5 h raw 100 Hz synth
  capture that goes through ingest_session and process_session (option C);
- run_nightly for every night, oldest first, so FR13 sees earlier flags.

Idempotent: users are found by email, window sessions have deterministic ids,
ingest dedups by sha256, surveys are skipped when already stored, and only nights
without night_features are run. The raw synth output is cached under
DATA_DIR/cache/synth/<key>, keyed by its parameters and seed; reset-demo keeps it.
Passwords and survey answers are never logged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import security
from backend.config import get_settings
from backend.models import (
    CaptureSession,
    NightFeaturesRow,
    PipelineRun,
    Profile,
    SurveyResponseRow,
    User,
    WindowEstimateRow,
    scoped,
)
from backend.schemas.contracts import RunStatus, SurveyResponse
from backend.services import runs
from csi_core.config import CoreConfig, get_config
from csi_core.synth import synth_night

log = logging.getLogger(__name__)

PASSWORD_ENV = "DEMO_PERSONA_PASSWORD"
POLICY_VERSION = "demo-personas-1"
_NS = uuid.UUID("6f1d3c52-8a0e-4b7e-9d55-1c0f3a7b2e90")  # deterministic ids for seeded rows

# Generator parameters from personas.md (synthetic, not thresholds).
HISTORY_NIGHTS = 13  # D-14 .. D-2
ONSET = time(23, 0)
ONSET_JITTER_MIN = 10.0
DURATION_H = (7.5, 0.25)  # mean, sd
SIGMA_RR = 0.5
RESTLESS = (0.05, 0.015)  # mean, sd
QUALITY = (0.8, 1.0)
PNR_DB = (6.0, 12.0)
DEMO_WINDOW_START = time(22, 30)  # demo night window part: 22:30 D-1 .. 04:30 D
DEMO_WINDOW_H = 6.0
DEMO_RAW_H = 1.5
RAW_FS = 100.0
RAW_N_SUB = 52


@dataclass(frozen=True)
class Persona:
    key: str
    email: str
    seed: int
    demo_rr: float
    demo_restless: float
    raw_motion_bursts: int
    history_rr: tuple[float, ...]  # one per history night, D-14 .. D-2
    weekly: dict[str, tuple[list[int], list[int]]] = field(default_factory=dict)
    mental_dip: bool = False
    # Sleep length per history night (mean, sd in hours). Default: the original generator.
    duration_h: tuple[float, float] = DURATION_H
    # Daily check-in centre values (mood, energy, stress, sleep_quality), 0-4.
    daily_base: tuple[int, int, int, int] = (3, 3, 1, 3)
    # Spaceflight-hazard context (docs/hazards.md): cabin air per night and a daily
    # body_cabin check-in. Off for the original three personas.
    hazards: bool = False
    cabin_co2: tuple[float, float] = (2.1, 0.2)  # ppCO2 mmHg mean, sd (synthetic)
    cabin_late_rise: tuple[float, ...] = ()  # added to the last len(...) nights
    late_symptoms: tuple[str, ...] = ()  # body_cabin keys answered yes on the last 2 days
    friction_external: int = 1


def _answers(*vals: int) -> list[int]:
    return list(vals)


PERSONAS: tuple[Persona, ...] = (
    Persona(
        key="steady",
        email="steady@ex.com",
        seed=101,
        demo_rr=14.0,
        demo_restless=0.05,
        raw_motion_bursts=1,
        history_rr=(14.0,) * HISTORY_NIGHTS,
        # (D-14 answers, D-7 answers): PHQ-2 1/1, GAD-2 1/1, WHO-5 68/68 (items sum 17)
        weekly={
            "phq2": (_answers(1, 0), _answers(1, 0)),
            "gad2": (_answers(1, 0), _answers(1, 0)),
            "who5": (_answers(4, 4, 3, 3, 3), _answers(4, 4, 3, 3, 3)),
        },
    ),
    Persona(
        key="breath-drift",
        email="drift@ex.com",
        seed=202,
        demo_rr=16.0,
        demo_restless=0.20,
        raw_motion_bursts=4,
        history_rr=(13.0,) * 9 + (13.6, 14.0, 14.4, 14.8),
        weekly={
            "phq2": (_answers(1, 0), _answers(1, 0)),
            "gad2": (_answers(1, 0), _answers(1, 0)),
            "who5": (_answers(4, 4, 3, 3, 3), _answers(4, 3, 3, 3, 3)),
        },  # 68, 64
    ),
    Persona(
        key="mental-dip",
        email="dip@ex.com",
        seed=303,
        demo_rr=15.0,
        demo_restless=0.05,
        raw_motion_bursts=1,
        history_rr=(15.0,) * HISTORY_NIGHTS,
        weekly={
            "phq2": (_answers(1, 0), _answers(2, 1)),  # 1, 3 (alert)
            "gad2": (_answers(1, 0), _answers(2, 1)),  # 1, 3 (alert)
            "who5": (_answers(4, 3, 3, 3, 3), _answers(3, 2, 2, 2, 2)),
        },  # 64, 44 (alert)
        mental_dip=True,
    ),
)
# NASA-calibrated crew (synthetic people; only the sleep length comes from published ISS
# actigraphy): Barger et al. 2014, Lancet Neurol 13:904 (in flight 6.09 +/- 0.67 h) and
# Flynn-Evans et al. 2016, npj Microgravity 2:16019 (circadian-aligned 6.4 +/- 1.2 h,
# misaligned 5.4 +/- 1.4 h). Breathing values are a stated design assumption, not NASA data.
ISS_PERSONAS: tuple[Persona, ...] = (
    Persona(
        key="iss-flight",
        email="iss-flight@ex.com",
        seed=404,
        demo_rr=16.0,
        demo_restless=0.20,
        raw_motion_bursts=4,
        history_rr=(13.0,) * 9 + (13.6, 14.0, 14.4, 14.8),  # slow breathing drift
        weekly={
            "phq2": (_answers(1, 0), _answers(1, 0)),
            "gad2": (_answers(1, 0), _answers(1, 0)),
            "who5": (_answers(4, 4, 3, 3, 3), _answers(4, 3, 3, 3, 3)),
        },
        duration_h=(6.09, 0.67),
        hazards=True,
        cabin_co2=(2.2, 0.2),
        cabin_late_rise=(0.4, 0.6, 0.9),  # a sleep-station CO2 pocket on the last nights
        late_symptoms=("sym_headache", "sym_stuffiness"),
        friction_external=2,
    ),
    Persona(
        key="iss-aligned",
        email="iss-aligned@ex.com",
        seed=505,
        demo_rr=14.0,
        demo_restless=0.05,
        raw_motion_bursts=1,
        history_rr=(14.0,) * HISTORY_NIGHTS,
        weekly={
            "phq2": (_answers(1, 0), _answers(1, 0)),
            "gad2": (_answers(1, 0), _answers(1, 0)),
            "who5": (_answers(4, 4, 3, 3, 3), _answers(4, 4, 3, 3, 3)),
        },
        duration_h=(6.4, 1.2),
        hazards=True,
        cabin_co2=(2.0, 0.15),
    ),
    Persona(
        key="iss-misaligned",
        email="iss-misaligned@ex.com",
        seed=606,
        demo_rr=15.0,
        demo_restless=0.05,
        raw_motion_bursts=1,
        history_rr=(15.0,) * HISTORY_NIGHTS,
        weekly={
            "phq2": (_answers(1, 0), _answers(2, 1)),
            "gad2": (_answers(1, 0), _answers(2, 1)),
            "who5": (_answers(4, 3, 3, 3, 3), _answers(3, 2, 2, 2, 2)),
        },
        mental_dip=True,
        duration_h=(5.4, 1.4),
        hazards=True,
        cabin_co2=(2.3, 0.2),
        late_symptoms=("sym_fatigue", "sym_drowsy", "sym_throat"),
        friction_external=3,
    ),
)
ALL_PERSONAS: tuple[Persona, ...] = PERSONAS + ISS_PERSONAS
FINAL_PHQ9 = {f"phq9_{i}": v for i, v in enumerate((2, 2, 2, 1, 1, 2, 1, 0, 1), start=1)}


# ----------------------------------------------------------------- users


def _ensure_user(db: Session, p: Persona, password: str | None) -> tuple[str, str | None]:
    """Return (user_id, generated_password_or_None). Never logs the password."""
    from backend.services import accounts

    uid = db.scalar(select(User.id).where(User.email == p.email))
    generated = None
    if uid is None:
        pw = password or os.environ.get(PASSWORD_ENV) or os.environ.get("DEMO_PASSWORD")
        if not pw:
            pw = generated = secrets.token_urlsafe(18)
        # Direct insert, not accounts.signup: the shared demo password may be shorter than
        # the sign-up minimum (synthetic demo accounts only; real sign-ups keep the rule).
        user = User(email=p.email, password_hash=security.hash_password(pw), is_synthetic=True)
        db.add(user)
        db.flush()
        db.add(Profile(user_id=user.id))
        uid = user.id
    user = db.get(User, uid)
    user.is_synthetic = True
    db.commit()
    accounts.set_consents(
        db, uid, {"checkins": True, "survey_answers": True}, policy_version=POLICY_VERSION
    )
    return uid, generated


# ----------------------------------------------------------------- surveys


def _at(day: date, hh: int) -> datetime:
    return datetime.combine(day, time(hh, 0), tzinfo=UTC)


def _submit(
    db: Session, uid: str, instrument_id: str, keys: list[str], vals: list[int], when: datetime
) -> dict | None:
    from backend.services import surveys

    if instrument_id not in surveys.CHECKIN_SLOTS:  # check-ins upsert by themselves
        exists = db.scalar(
            scoped(
                select(func.count())
                .select_from(SurveyResponseRow)
                .where(
                    SurveyResponseRow.instrument_id == instrument_id,
                    SurveyResponseRow.administered_at == when,
                ),
                SurveyResponseRow,
                uid,
            )
        )
        if exists:
            return None
    inst = surveys.get_instrument(db, instrument_id)
    data = SurveyResponse(
        user_id=uid,
        instrument_id=instrument_id,
        instrument_version=inst["version"],
        administered_at=when,
        answers=dict(zip(keys, vals, strict=True)),
    )
    return surveys.submit_response(db, uid, data)


def _item_keys(db: Session, instrument_id: str) -> list[str]:
    from backend.services import surveys

    return [it["key"] for it in surveys.get_instrument(db, instrument_id)["items"]]


def _daily_values(p: Persona, i: int, rng: np.random.Generator) -> dict[str, int]:
    """Day i of 14 (0 = D-14). Steady: 3/3/3, stress 1, +-1 jitter.
    P3 from D-7: mood 3->1, energy 3->1, stress 1->3, linear, no jitter."""
    if p.mental_dip and i >= 7:
        f = (i - 7) / 6
        mood, energy, stress = round(3 - 2 * f), round(3 - 2 * f), round(1 + 2 * f)
        return {"mood": mood, "energy": energy, "stress": stress, "sleep_quality": 3}

    def j(v: int) -> int:
        return int(np.clip(v + rng.integers(-1, 2), 0, 4))

    mood, energy, stress, slept = p.daily_base
    return {"mood": j(mood), "energy": j(energy), "stress": j(stress), "sleep_quality": j(slept)}


def seed_surveys_for_day(db: Session, p: Persona, uid: str, anchor: date, i: int) -> int:
    """Surveys administered on day i (0 = D-14 .. 13 = D-1): daily AM/PM, and the
    weekly instruments on D-14 and D-7. Returns the number of new submissions."""
    day = anchor - timedelta(days=14 - i)
    v = _daily_values(p, i, np.random.default_rng(p.seed * 1000 + i))
    n = 0
    for inst, hh in (("daily_am", 7), ("daily_pm", 21)):
        keys = _item_keys(db, inst)
        if _submit(db, uid, inst, keys, [v[k] for k in keys], _at(day, hh)):
            n += 1
    for inst, (first, second) in p.weekly.items():
        for vals, days_before in ((first, 14), (second, 7)):
            if 14 - i == days_before and _submit(
                db, uid, inst, _item_keys(db, inst), vals, _at(day, 12)
            ):
                n += 1
    return n


def seed_hazards_for_day(db: Session, p: Persona, uid: str, anchor: date, i: int) -> int:
    """Cabin air for night i and that day's body_cabin check-in (synthetic; never a red flag)."""
    from backend.models import CabinReading

    day = anchor - timedelta(days=14 - i)
    rng = np.random.default_rng(p.seed * 7000 + i)
    late = len(p.cabin_late_rise)
    rise = p.cabin_late_rise[i - (14 - late)] if late and i >= 14 - late else 0.0
    have = db.scalar(
        scoped(select(CabinReading).where(CabinReading.date == day), CabinReading, uid)
    )
    if have is None:
        db.add(CabinReading(
            user_id=uid, date=day, source="synthetic",
            ppco2_mmhg=round(float(max(1.0, rng.normal(*p.cabin_co2))) + rise, 2),
            temp_c=round(float(rng.normal(22.5, 0.6)), 1),
            rh_pct=round(float(rng.normal(45, 4)), 0),
        ))
        db.commit()
    keys = _item_keys(db, "body_cabin")
    yes = set(p.late_symptoms) if i >= 12 else set()
    vals = {k: (1 if k in yes else 0) for k in keys}
    vals["exercise_min"] = int(rng.choice([30, 45, 60, 90]))
    vals["exercise_effort"] = int(rng.integers(3, 7))
    vals["friction_crew"] = int(rng.integers(0, 2))
    vals["friction_external"] = int(min(4, p.friction_external + (1 if i >= 12 else 0)))
    return 1 if _submit(db, uid, "body_cabin", keys, [vals[k] for k in keys], _at(day, 20)) else 0


def seed_final_phq9(db: Session, p: Persona, uid: str, anchor: date) -> int:
    """P3's PHQ-9 on D (normally submitted live in the demo, never by default)."""
    if not p.mental_dip:
        return 0
    keys = _item_keys(db, "phq9")
    return int(bool(_submit(db, uid, "phq9", keys, [FINAL_PHQ9[k] for k in keys], _at(anchor, 9))))


# ----------------------------------------------------------------- window-level nights


def _window_rows(
    uid: str,
    sid: str,
    onset: datetime,
    hours: float,
    rr: float,
    restless: float,
    rng: np.random.Generator,
    cfg: CoreConfig,
) -> list[WindowEstimateRow]:
    win, step = cfg.breath.window_s, cfg.breath.step_s
    n = int((hours * 3600 - win) // step) + 1
    motion = np.zeros(n, dtype=bool)
    motion[rng.choice(n, size=int(round(np.clip(restless, 0, 1) * n)), replace=False)] = True
    q = rng.uniform(*QUALITY, n)
    pnr = rng.uniform(*PNR_DB, n)
    rows = []
    for i in range(n):
        a = onset + timedelta(seconds=i * step)
        moving = bool(motion[i])
        rows.append(
            WindowEstimateRow(
                user_id=uid,
                session_id=sid,
                t_start=a,
                t_end=a + timedelta(seconds=win),
                rr_a=None if moving else rr,
                rr_b=None if moving else rr,
                pnr_db=float(pnr[i]),
                motion_flag=moving,
                quality=float(q[i]),
                presence=True,
            )
        )
    return rows


def _night_plan(p: Persona, anchor: date, full_demo: bool = False) -> list[dict[str, Any]]:
    """Window-level parts: 13 history nights + the demo night's 6 h part. ``full_demo``
    (no raw capture seeded) covers the raw part's hours with windows too, so the demo night
    keeps its usual length and mid-sleep time."""
    plan = []
    for k in range(HISTORY_NIGHTS):
        night = anchor - timedelta(days=14 - k)
        rng = np.random.default_rng(p.seed * 100 + k)
        onset = datetime.combine(night, ONSET, tzinfo=UTC) + timedelta(
            minutes=float(rng.normal(0, ONSET_JITTER_MIN))
        )
        plan.append(
            {
                "night": night,
                "onset": onset,
                "rng": rng,
                "hours": float(rng.normal(*p.duration_h)),
                "rr": float(rng.normal(p.history_rr[k], SIGMA_RR)),
                "restless": float(np.clip(rng.normal(*RESTLESS), 0.0, 1.0)),
            }
        )
    demo = anchor - timedelta(days=1)
    plan.append(
        {
            "night": demo,
            "onset": datetime.combine(demo, DEMO_WINDOW_START, tzinfo=UTC),
            "rng": np.random.default_rng(p.seed * 100 + HISTORY_NIGHTS),
            "hours": DEMO_WINDOW_H + (DEMO_RAW_H if full_demo else 0.0),
            "rr": p.demo_rr,
            "restless": p.demo_restless,
        }
    )
    return plan


def _window_session_key(p: Persona, night: date) -> tuple[str, str]:
    key = f"{p.email}:{night.isoformat()}:windows"
    return key, str(uuid.uuid5(_NS, key))


def _missing_window_nights(db: Session, p: Persona, anchor: date) -> list[date]:
    nights = [anchor - timedelta(days=k) for k in range(14, 0, -1)]
    return [n for n in nights if db.get(CaptureSession, _window_session_key(p, n)[1]) is None]


def seed_windows(
    db: Session,
    p: Persona,
    uid: str,
    anchor: date,
    run_id: str | None,
    cfg: CoreConfig,
    full_demo: bool = False,
) -> int:
    """One synthetic session + its windows per planned night. Skips existing sessions."""
    n = 0
    for night in _night_plan(p, anchor, full_demo):
        key, sid = _window_session_key(p, night["night"])
        if db.get(CaptureSession, sid) is not None:
            continue
        rows = _window_rows(
            uid,
            sid,
            night["onset"],
            night["hours"],
            night["rr"],
            night["restless"],
            night["rng"],
            cfg,
        )
        for r in rows:
            r.run_id = run_id
        db.add(
            CaptureSession(
                id=sid,
                user_id=uid,
                start_utc=rows[0].t_start,
                end_utc=rows[-1].t_end,
                condition="persona_window_seed",
                room_notes=f"persona={p.key} seed={p.seed}",
                source_kind="synthetic",
                raw_path=f"raw/{sid}",
                raw_sha256=hashlib.sha256(key.encode()).hexdigest(),
                usable=False,
                run_id=run_id,
            )
        )
        db.flush()
        db.add_all(rows)
        n += len(rows)
    return n


def seed_windows_handler(db: Session, run: PipelineRun) -> str:
    prm = run.parameters
    p = next(x for x in ALL_PERSONAS if x.key == prm["persona"])
    n = seed_windows(
        db, p, prm["user_id"], date.fromisoformat(prm["anchor"]), run.id, get_config(),
        full_demo=bool(prm.get("full_demo")),
    )
    return f"seed_persona_windows persona={p.key} windows={n}"


# ----------------------------------------------------------------- raw demo part


def _cache_root() -> Path:
    return get_settings().data_dir / "cache" / "synth"


def raw_demo_dir(
    p: Persona, anchor: date, *, fs: float, n_sub: int, cache_root: Path | None = None
) -> Path:
    """Generate (or reuse) the 1.5 h raw synth capture for the demo night."""
    start = datetime.combine(anchor, time(4, 30), tzinfo=UTC)
    params = {
        "start_utc": start.isoformat(),
        "hours": DEMO_RAW_H,
        "rr_bpm": p.demo_rr,
        "fs": fs,
        "n_sub": n_sub,
        "motion_bursts": p.raw_motion_bursts,
        "seed": p.seed,
    }
    key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
    root = cache_root or _cache_root()
    final = root / f"{p.key}-{key}"
    if (final / "markers.csv").is_file():
        return final
    tmp = root / f".tmp-{p.key}-{key}"
    shutil.rmtree(tmp, ignore_errors=True)
    synth_night(
        tmp,
        start_utc=start,
        hours=DEMO_RAW_H,
        rr_bpm=p.demo_rr,
        fs=fs,
        n_sub=n_sub,
        motion_bursts=p.raw_motion_bursts,
        seed=p.seed,
        extra_markers=[(0.0, "demo_night")],
    )
    tmp.rename(final)
    return final


def _run_kind(db: Session, kind: str, params: dict, user_id: str) -> None:
    rec = runs.execute(db, runs.create_run(db, kind, params, [], user_id=user_id).id)
    if rec.status is not RunStatus.succeeded:
        raise RuntimeError(f"{kind} failed: {rec.log.strip().splitlines()[-1]}")


def seed_raw(
    db: Session,
    p: Persona,
    uid: str,
    anchor: date,
    *,
    fs: float,
    n_sub: int,
    cache_root: Path | None,
) -> str:
    from backend.services.ingestion import ingest_session

    src = raw_demo_dir(p, anchor, fs=fs, n_sub=n_sub, cache_root=cache_root)
    sess = ingest_session(db, uid, src)
    if not sess.usable:
        raise RuntimeError(f"demo raw session for {p.key} is not usable")
    has_windows = db.scalar(
        scoped(
            select(func.count())
            .select_from(WindowEstimateRow)
            .where(WindowEstimateRow.session_id == sess.id),
            WindowEstimateRow,
            uid,
        )
    )
    if not has_windows:
        _run_kind(db, "process_session", {"session_id": sess.id}, uid)
    return sess.id


# ----------------------------------------------------------------- entry point


def seed(
    db: Session,
    *,
    anchor: date,
    password: str | None = None,
    include_final_phq9: bool = False,
    raw_fs: float = RAW_FS,
    raw_n_sub: int = RAW_N_SUB,
    cache_root: Path | None = None,
    with_iss: bool = False,
    with_raw: bool = True,
) -> dict[str, Any]:
    """Seed all personas for demo day ``anchor`` (plus the NASA-calibrated ISS crew when
    ``with_iss``). Safe to re-run: existing personas are only topped up. ``with_raw=False``
    skips the synthetic raw CSI capture (~850 MB peak to synthesise); nights are then built
    from the seeded breathing windows only. Used on small cloud hosts."""
    from backend.services import surveys

    out: dict[str, Any] = {"anchor": anchor.isoformat(), "personas": []}
    for p in ALL_PERSONAS if with_iss else PERSONAS:
        uid, generated = _ensure_user(db, p, password)
        surveys.load_catalog(db)
        if _missing_window_nights(db, p, anchor):  # no run row at all on a no-op reseed
            _run_kind(
                db,
                "seed_persona_windows",
                {"persona": p.key, "user_id": uid, "anchor": anchor.isoformat(),
                 "full_demo": not with_raw},
                uid,
            )
        entry = _seed_rest(
            db, p, uid, anchor, with_raw=with_raw, include_final_phq9=include_final_phq9,
            raw_fs=raw_fs, raw_n_sub=raw_n_sub, cache_root=cache_root,
        )
        if generated:
            entry["generated_password"] = generated  # shown once by the CLI, never logged
        out["personas"].append(entry)
        log.info("persona seeded key=%s nights_run=%d", p.key, entry["nights_run"])
    return out


def _seed_rest(
    db: Session,
    p: Persona,
    uid: str,
    anchor: date,
    *,
    with_raw: bool,
    include_final_phq9: bool = False,
    raw_fs: float = RAW_FS,
    raw_n_sub: int = RAW_N_SUB,
    cache_root: Path | None = None,
) -> dict[str, Any]:
    """After the windows exist: raw capture (optional), surveys and nightly runs."""
    raw_sid = (
        seed_raw(db, p, uid, anchor, fs=raw_fs, n_sub=raw_n_sub, cache_root=cache_root)
        if with_raw
        else None
    )
    # Chronological: a night only sees surveys submitted up to that day, so the
    # backfill does not leak later answers into earlier nights.
    done = set(db.scalars(scoped(select(NightFeaturesRow.date), NightFeaturesRow, uid)))
    ran = n_surveys = 0
    for i in range(14):
        night = anchor - timedelta(days=14 - i)
        n_surveys += seed_surveys_for_day(db, p, uid, anchor, i)
        if p.hazards:
            n_surveys += seed_hazards_for_day(db, p, uid, anchor, i)
        if night not in done:
            _run_kind(db, "run_nightly", {"user_id": uid, "day": night.isoformat()}, uid)
            ran += 1
    if include_final_phq9:
        n_surveys += seed_final_phq9(db, p, uid, anchor)
    return {
        "key": p.key,
        "email": p.email,
        "user_id": uid,
        "raw_session_id": raw_sid,
        "survey_submissions": n_surveys,
        "nights_run": ran,
    }


# ----------------------------------------------------------------- visitor's own synthetic data

SLEEP_SD_BY_REGULARITY = (1.4, 1.1, 0.8, 0.5, 0.25)  # 0 very irregular .. 4 very regular


def custom_persona(email: str, profile: dict[str, Any], seed: int) -> Persona:
    """A synthetic persona from a demo visitor's 5 answers (synthetic data knobs only, never a
    clinical judgement). No PHQ-9 is generated, so the safety item is never simulated."""
    hours = float(min(10.0, max(4.0, profile["sleep_hours"])))
    reg = int(min(4, max(0, profile["regularity"])))
    stress = int(min(4, max(0, profile["stress"])))
    mood = int(min(4, max(0, profile["mood"])))
    change = bool(profile["recent_change"])
    energy = int(round((mood + (4 - stress)) / 2))
    base = 14.0
    rr = (base,) * 9 + (base + 0.6, base + 1.0, base + 1.4, base + 1.8) if change \
        else (base,) * HISTORY_NIGHTS
    gad = (0, 0, 1, 2, 3)[stress]
    phq = (2, 1, 1, 0, 0)[mood]
    who = (1, 2, 3, 4, 5)[mood]
    return Persona(
        key=f"visitor-{seed}",
        email=email,
        seed=seed,
        demo_rr=base + (3.0 if change else 0.0),
        demo_restless=0.20 if change else 0.05,
        raw_motion_bursts=1,
        history_rr=rr,
        weekly={
            "phq2": (_answers(phq, phq), _answers(phq, phq)),
            "gad2": (_answers(gad, gad), _answers(gad, gad)),
            "who5": (_answers(*(who,) * 5), _answers(*(who,) * 5)),
        },
        mental_dip=mood <= 1 or stress >= 3,
        duration_h=(hours, SLEEP_SD_BY_REGULARITY[reg]),
        hazards=True,
        late_symptoms=("sym_fatigue", "sym_headache") if change else (),
        friction_external=min(4, stress),
        daily_base=(mood, energy, stress, max(0, min(4, round((hours - 4) / 1.25)))),
    )


def seed_visitor(db: Session, uid: str, email: str, profile: dict[str, Any]) -> None:
    """Fill a fresh visitor account with 14 synthetic nights + check-ins from its answers."""
    from backend.services import accounts, surveys

    p = custom_persona(email, profile, seed=int(uuid.UUID(uid).int % 1_000_000) + 1000)
    anchor = datetime.now(UTC).date()
    accounts.set_consents(
        db, uid, {"checkins": True, "survey_answers": True}, policy_version=POLICY_VERSION
    )
    surveys.load_catalog(db)
    seed_windows(db, p, uid, anchor, None, get_config(), full_demo=True)
    _seed_rest(db, p, uid, anchor, with_raw=False)


RUN_KINDS = {"seed_persona_windows": seed_windows_handler}

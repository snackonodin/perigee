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

from backend.config import get_settings
from backend.models import (
    CaptureSession,
    NightFeaturesRow,
    PipelineRun,
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


def _answers(*vals: int) -> list[int]:
    return list(vals)


PERSONAS: tuple[Persona, ...] = (
    Persona(
        key="steady",
        email="persona-steady@example.invalid",
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
        email="persona-drift@example.invalid",
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
        email="persona-dip@example.invalid",
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
FINAL_PHQ9 = {f"phq9_{i}": v for i, v in enumerate((2, 2, 2, 1, 1, 2, 1, 0, 1), start=1)}


# ----------------------------------------------------------------- users


def _ensure_user(db: Session, p: Persona, password: str | None) -> tuple[str, str | None]:
    """Return (user_id, generated_password_or_None). Never logs the password."""
    from backend.services import accounts

    uid = db.scalar(select(User.id).where(User.email == p.email))
    generated = None
    if uid is None:
        pw = password or os.environ.get(PASSWORD_ENV)
        if not pw:
            pw = generated = secrets.token_urlsafe(18)
        uid = accounts.signup(db, p.email, pw).user_id
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

    return {"mood": j(3), "energy": j(3), "stress": j(1), "sleep_quality": j(3)}


def seed_surveys(db: Session, p: Persona, uid: str, anchor: date, *, final_phq9: bool) -> int:
    from backend.services import surveys

    surveys.load_catalog(db)
    n = 0
    am_keys, pm_keys = _item_keys(db, "daily_am"), _item_keys(db, "daily_pm")
    for i in range(14):
        day = anchor - timedelta(days=14 - i)
        rng = np.random.default_rng(p.seed * 1000 + i)
        v = _daily_values(p, i, rng)
        _submit(db, uid, "daily_am", am_keys, [v[k] for k in am_keys], _at(day, 7))
        _submit(db, uid, "daily_pm", pm_keys, [v[k] for k in pm_keys], _at(day, 21))
        n += 2
    for inst, (first, second) in p.weekly.items():
        keys = _item_keys(db, inst)
        for vals, days_before in ((first, 14), (second, 7)):
            if _submit(db, uid, inst, keys, vals, _at(anchor - timedelta(days=days_before), 12)):
                n += 1
    if final_phq9 and p.mental_dip:
        keys = _item_keys(db, "phq9")
        if _submit(db, uid, "phq9", keys, [FINAL_PHQ9[k] for k in keys], _at(anchor, 9)):
            n += 1
    return n


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


def _night_plan(p: Persona, anchor: date) -> list[dict[str, Any]]:
    """Window-level parts: 13 history nights + the demo night's 6 h part."""
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
                "hours": float(rng.normal(*DURATION_H)),
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
            "hours": DEMO_WINDOW_H,
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
    db: Session, p: Persona, uid: str, anchor: date, run_id: str | None, cfg: CoreConfig
) -> int:
    """One synthetic session + its windows per planned night. Skips existing sessions."""
    n = 0
    for night in _night_plan(p, anchor):
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


@runs.register("seed_persona_windows")
def seed_windows_handler(db: Session, run: PipelineRun) -> str:
    prm = run.parameters
    p = next(x for x in PERSONAS if x.key == prm["persona"])
    n = seed_windows(db, p, prm["user_id"], date.fromisoformat(prm["anchor"]), run.id, get_config())
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


def _run_kind(db: Session, kind: str, params: dict) -> None:
    rec = runs.execute(db, runs.create_run(db, kind, params, []).id)
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
        _run_kind(db, "process_session", {"session_id": sess.id, "user_id": uid})
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
) -> dict[str, Any]:
    """Seed all personas for demo day ``anchor``. Safe to re-run."""
    out: dict[str, Any] = {"anchor": anchor.isoformat(), "personas": []}
    for p in PERSONAS:
        uid, generated = _ensure_user(db, p, password)
        n_surveys = seed_surveys(db, p, uid, anchor, final_phq9=include_final_phq9)
        if _missing_window_nights(db, p, anchor):  # no run row at all on a no-op reseed
            _run_kind(
                db,
                "seed_persona_windows",
                {"persona": p.key, "user_id": uid, "anchor": anchor.isoformat()},
            )
        raw_sid = seed_raw(db, p, uid, anchor, fs=raw_fs, n_sub=raw_n_sub, cache_root=cache_root)
        done = set(db.scalars(scoped(select(NightFeaturesRow.date), NightFeaturesRow, uid)))
        ran = 0
        for k in range(14, 0, -1):
            night = anchor - timedelta(days=k)
            if night not in done:
                _run_kind(db, "run_nightly", {"user_id": uid, "day": night.isoformat()})
                ran += 1
        entry = {
            "key": p.key,
            "email": p.email,
            "user_id": uid,
            "raw_session_id": raw_sid,
            "survey_submissions": n_surveys,
            "nights_run": ran,
        }
        if generated:
            entry["generated_password"] = generated  # shown once by the CLI, never logged
        out["personas"].append(entry)
        log.info("persona seeded key=%s nights_run=%d", p.key, ran)
    return out


RUN_KINDS = {"seed_persona_windows": seed_windows_handler}

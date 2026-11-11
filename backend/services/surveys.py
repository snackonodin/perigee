"""Instrument catalog, safety check, scoring and survey submission (FR16-FR18).

Red-class data: survey answers are never logged, printed or put in exception
messages. Log only instrument ids, response ids and counts.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import Callable
from datetime import UTC
from functools import lru_cache
from typing import Any

from backend.schemas.contracts import SafetyResult, SurveyResponse
from csi_core.config import ROOT

log = logging.getLogger(__name__)

SEEDS_DIR = ROOT / "seeds"
INSTRUMENTS_DIR = SEEDS_DIR / "instruments"

# Used only if seeds/safety_resources.json cannot be read: the safety path
# must never fail because of a missing or broken file.
_FALLBACK_RESOURCES = [
    "Contact your flight surgeon or your designated support contact now.",
    "If you are in immediate danger, call your local emergency number now.",
]
_FALLBACK_REASON = "You do not have to handle this alone. Please reach out now."


# --------------------------------------------------------------------------- catalog (pure)


@lru_cache(maxsize=1)
def _seed_catalog() -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    for path in sorted(INSTRUMENTS_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        catalog[doc["id"]] = doc
    return catalog


def load_seed_catalog() -> dict[str, dict]:
    """All instruments from seeds/instruments, keyed by id. Returns deep copies."""
    return json.loads(json.dumps(_seed_catalog()))


def get_seed_instrument(instrument_id: str) -> dict:
    try:
        return load_seed_catalog()[instrument_id]
    except KeyError:
        raise UnknownInstrument(instrument_id) from None


class UnknownInstrument(LookupError):
    pass


# --------------------------------------------------------------------------- safety (pure)


@lru_cache(maxsize=1)
def _safety_resources() -> tuple[str, tuple[str, ...]]:
    try:
        doc = json.loads((SEEDS_DIR / "safety_resources.json").read_text(encoding="utf-8"))
        reason = doc["reasons"]["safety_item"]
        resources = tuple(str(r) for r in doc["resources"])
        if not resources:
            raise ValueError("empty resources")
        return reason, resources
    except Exception:  # never let the safety path fail on a seed file
        log.exception("safety_resources.json unreadable; using built-in fallback")
        return _FALLBACK_REASON, tuple(_FALLBACK_RESOURCES)


def safety_check(instrument: dict, answers: dict[str, int]) -> SafetyResult:
    """Pure and synchronous. Never queued, never touches the DB.

    Any item with ``safety_trigger`` fires when its answer is >= min_value.
    A present-but-uncomparable answer on a safety item also fires: when in
    doubt, show the safety screen.
    """
    for item in instrument.get("items", []):
        trigger = item.get("safety_trigger")
        if not trigger or item["key"] not in answers:
            continue
        value = answers[item["key"]]
        try:
            fired = value >= trigger["min_value"]
        except TypeError:
            fired = True
        if fired:
            reason, resources = _safety_resources()
            return SafetyResult(show=True, reason=reason, resources=list(resources))
    return SafetyResult(show=False)


# --------------------------------------------------------------------------- scoring (pure)


class InvalidAnswers(ValueError):
    """Answers do not match the instrument. ``errors`` name item keys only, never values."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"{len(errors)} invalid answer(s)")
        self.errors = errors


def validate_answers(instrument: dict, answers: dict[str, int]) -> None:
    """Every item answered exactly once with one of its option values; no extra keys."""
    errors: list[str] = []
    items = {it["key"]: it for it in instrument["items"]}
    for key in answers:
        if key not in items:
            errors.append(f"unknown item: {key}")
    for key, item in items.items():
        if key not in answers:
            errors.append(f"missing item: {key}")
            continue
        value = answers[key]
        allowed = {o["value"] for o in item["options"]}
        if isinstance(value, bool) or not isinstance(value, int) or value not in allowed:
            errors.append(f"value not an allowed option: {key}")
    if errors:
        raise InvalidAnswers(errors)


def _band(ranges: list[dict], score: float) -> str | None:
    for r in ranges:
        if r["min"] <= score <= r["max"]:
            return r["label"]
    return None


def score_answers(instrument: dict, answers: dict[str, int]) -> dict:
    """Validate, then score from the catalog entry alone.

    Returns {"total": raw sum, "score": scaled score, "band": label | None,
    "method": ..., "items": {...} only for per-item check-ins}.
    ``sum`` -> score = total; ``sum_x4`` -> score = total * 4 (WHO-5 percentage).
    Bands come only from the instrument JSON (cited or empty).
    """
    validate_answers(instrument, answers)
    scoring = instrument["scoring"]
    method = scoring["method"]
    total = sum(answers[it["key"]] for it in instrument["items"])
    if method == "sum":
        score = total
    elif method == "sum_x4":
        score = total * 4
    else:
        raise ValueError(f"unknown scoring method for {instrument['id']}: {method}")
    result: dict = {
        "total": total,
        "score": score,
        "band": _band(scoring.get("ranges", []), score),
        "method": method,
    }
    if scoring.get("per_item"):
        result["items"] = {it["key"]: answers[it["key"]] for it in instrument["items"]}
    return result


# --------------------------------------------------------------------------- DB-backed
#
# Models come from backend.models (merged from feat/db-ingest) and encrypt() from
# backend.security (feat/accounts). Both are imported lazily, so that
# safety_check keeps working with no DB. Tests swap the encoder with
# set_encryptor() until EncryptedJSON / encrypt() is merged.

CHECKIN_SLOTS = {"daily_am": "am", "daily_pm": "pm"}  # amber: stored in checkins_daily
CONSENT_CHECKINS = "checkins"
CONSENT_SURVEY_ANSWERS = "survey_answers"

_ENCRYPT: Callable[[bytes], bytes] | None = None


def set_encryptor(fn: Callable[[bytes], bytes] | None) -> None:
    global _ENCRYPT
    _ENCRYPT = fn


def _models() -> Any:
    import backend.models as m

    return m


def _encrypt(data: bytes) -> bytes:
    if _ENCRYPT is not None:
        return _ENCRYPT(data)
    from backend.security import encrypt  # MERGE: arrives with feat/accounts

    return encrypt(data)


def _canonical(answers: dict[str, int]) -> bytes:
    return json.dumps(answers, sort_keys=True, separators=(",", ":")).encode()


def encode_answers(answers: dict[str, int]) -> bytes:
    """Answers -> ciphertext for SurveyResponseRow.answers (never stored in plaintext)."""
    return _encrypt(_canonical(answers))


def answers_digest(answers: dict[str, int]) -> str:
    """Keyed HMAC-SHA256 of the answers, for when survey_answers consent is off.

    Keyed, not a plain hash: the answer space is tiny (PHQ-9 has 4**9 combinations),
    so an unkeyed hash could be reversed by enumeration.
    """
    from backend.config import get_settings

    key = hashlib.sha256(b"survey-answers-digest-v1|" + get_settings().secret_key.encode()).digest()
    return hmac.new(key, _canonical(answers), hashlib.sha256).hexdigest()


def has_consent(db: Any, user_id: str, scope: str) -> bool:
    """True only if a consent row exists and is granted. No row means no consent."""
    from sqlalchemy import select

    m = _models()
    stmt = m.scoped(select(m.Consent.granted).where(m.Consent.scope == scope), m.Consent, user_id)
    return bool(db.scalars(stmt).first())


class SubmissionError(Exception):
    """Raised by submit_response. Always carries the safety result, so the caller
    can show the safety screen even when the submission itself fails."""

    def __init__(self, kind: str, safety: SafetyResult, errors: list[str] | None = None) -> None:
        super().__init__(f"submission failed: {kind}")
        self.kind = kind  # "invalid" | "unknown_instrument" | "forbidden" | "storage"
        self.safety = safety
        self.errors = errors or []


def load_catalog(db: Any) -> None:
    """Idempotent upsert of every seed instrument, keyed by (instrument_id, version)."""
    from sqlalchemy import select

    m = _models()
    for inst_id, doc in load_seed_catalog().items():
        row = db.scalars(
            select(m.Instrument).where(
                m.Instrument.instrument_id == inst_id, m.Instrument.version == doc["version"]
            )
        ).first()
        fields = {
            "name": doc["name"],
            "timeframe": doc.get("timeframe"),
            "license_note": doc.get("license_note"),
            "source_url": doc.get("source_url"),
            "definition": doc,
        }
        if row is None:
            db.add(m.Instrument(instrument_id=inst_id, version=doc["version"], **fields))
        else:
            for k, v in fields.items():
                setattr(row, k, v)
    db.commit()
    log.info("instrument catalog loaded: %d instruments", len(_seed_catalog()))


def get_instrument(db: Any, instrument_id: str, version: str | None = None) -> dict:
    """The catalog definition. Without ``version``, the most recently updated one."""
    from sqlalchemy import select

    m = _models()
    stmt = select(m.Instrument).where(m.Instrument.instrument_id == instrument_id)
    if version is not None:
        stmt = stmt.where(m.Instrument.version == version)
    row = db.scalars(stmt.order_by(m.Instrument.updated_at.desc())).first()
    if row is None:
        raise UnknownInstrument(instrument_id)
    return json.loads(json.dumps(row.definition))


def _instrument_for_safety(db: Any, instrument_id: str) -> dict | None:
    # Seeds first: pure, cached, no DB, so a DB failure cannot hide the safety screen.
    try:
        return get_seed_instrument(instrument_id)
    except UnknownInstrument:
        pass
    try:
        return get_instrument(db, instrument_id)
    except Exception:
        return None


def _record_safety_event(db: Any, user_id: str, instrument_id: str) -> None:
    """Minimal row (no answers), committed on its own before anything else is stored."""
    m = _models()
    try:
        db.add(
            m.SafetyEvent(user_id=user_id, source=f"survey:{instrument_id}", reason="safety_item")
        )
        db.commit()
    except Exception:
        db.rollback()
        log.error("safety event could not be stored (instrument=%s)", instrument_id)


def submit_response(db: Any, user_id: str, data: SurveyResponse) -> dict:
    """Safety first, then validate, score and store.

    Returns {"id", "total", "scores", "safety"}. On failure raises SubmissionError,
    which still carries the safety result.
    """
    # 1. Safety, before any validation. Synchronous, never queued.
    safety_inst = _instrument_for_safety(db, data.instrument_id)
    safety = safety_check(safety_inst, data.answers) if safety_inst else SafetyResult(show=False)
    if safety.show:
        _record_safety_event(db, user_id, data.instrument_id)

    # 2. Ownership, instrument + version, answers.
    if data.user_id != user_id:
        raise SubmissionError("forbidden", safety)
    try:
        get_instrument(db, data.instrument_id)
    except UnknownInstrument:
        raise SubmissionError("unknown_instrument", safety) from None
    try:
        instrument = get_instrument(db, data.instrument_id, data.instrument_version)
    except UnknownInstrument:
        raise SubmissionError("invalid", safety, ["instrument_version not in catalog"]) from None
    try:
        scored = score_answers(instrument, data.answers)
    except InvalidAnswers as e:
        raise SubmissionError("invalid", safety, e.errors) from None

    # 3. Store, gated on consent. Answers are never logged.
    try:
        if instrument["id"] in CHECKIN_SLOTS:
            row_id = _store_checkin(db, user_id, instrument, data)
        else:
            row_id = _store_survey(db, user_id, instrument, data, scored)
    except Exception:
        db.rollback()
        log.error("response could not be stored (instrument=%s)", instrument["id"])
        raise SubmissionError("storage", safety) from None
    log.info(
        "response handled id=%s instrument=%s stored=%s",
        row_id,
        instrument["id"],
        row_id is not None,
    )
    return {
        "id": row_id,
        "stored": row_id is not None,
        "total": scored["total"],
        "scores": {k: v for k, v in scored.items() if k != "total"},
        "safety": safety.model_dump(),
    }


def _store_survey(
    db: Any, user_id: str, instrument: dict, data: SurveyResponse, scored: dict
) -> str:
    """survey_responses. With survey_answers consent: encrypted answers + scores.
    Without: no answers; only total, score/band and a keyed digest."""
    m = _models()
    scores = {k: v for k, v in scored.items() if k != "total"}
    if has_consent(db, user_id, CONSENT_SURVEY_ANSWERS):
        answers = encode_answers(data.answers)
    else:
        answers = b""  # answers_enc is NOT NULL; empty means "not retained"
        scores = {
            "score": scored["score"],
            "band": scored["band"],
            "method": scored["method"],
            "answers_hmac": answers_digest(data.answers),
            "answers_retained": False,
        }
    row = m.SurveyResponseRow(
        user_id=user_id,
        instrument_id=instrument["id"],
        instrument_version=instrument["version"],
        administered_at=data.administered_at.astimezone(UTC),
        answers=answers,
        total=scored["total"],
        scores=scores,
    )
    db.add(row)
    db.commit()
    return row.id


def _store_checkin(db: Any, user_id: str, instrument: dict, data: SurveyResponse) -> str | None:
    """checkins_daily (amber, plain JSON). Upsert on (user_id, date, slot).
    Nothing is stored without checkins consent."""
    from sqlalchemy import select

    if not has_consent(db, user_id, CONSENT_CHECKINS):
        return None
    m = _models()
    slot = CHECKIN_SLOTS[instrument["id"]]
    day = data.administered_at.astimezone(UTC).date()
    stmt = m.scoped(
        select(m.CheckinDaily).where(m.CheckinDaily.date == day, m.CheckinDaily.slot == slot),
        m.CheckinDaily,
        user_id,
    )
    row = db.scalars(stmt).first()
    if row is None:
        row = m.CheckinDaily(user_id=user_id, date=day, slot=slot)
        db.add(row)
    row.instrument_id = instrument["id"]
    row.instrument_version = instrument["version"]
    row.answers = dict(data.answers)
    db.commit()
    return row.id

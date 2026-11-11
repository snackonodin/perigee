"""Instrument catalog, safety check, scoring and survey submission (FR16-FR18).

Red-class data: survey answers are never logged, printed or put in exception
messages. Log only instrument ids, response ids and counts.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from backend.schemas.contracts import SafetyResult

log = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).resolve().parents[2] / "seeds"
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

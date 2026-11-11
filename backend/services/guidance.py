"""Guidance cards (F10): conservative, non-diagnostic tips chosen by flag state.

The card text and matching rules live in seeds/guidance_cards.json. Selection is
a pure function of (flag state, deviating signals); the DB is only used to read
the user's flag (scoped) and record which cards were shown.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, time
from functools import lru_cache
from typing import Any

from csi_core.config import ROOT

log = logging.getLogger(__name__)

CARDS_PATH = ROOT / "seeds" / "guidance_cards.json"
MAX_CARDS = 3  # UI choice (how many cards to show at once), not a clinical value


class UnknownFlag(LookupError):
    pass


# --------------------------------------------------------------------------- pure


@lru_cache(maxsize=1)
def _cards() -> tuple[dict, ...]:
    doc = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    return tuple(doc["cards"])


def load_seed_cards() -> list[dict]:
    return json.loads(json.dumps(list(_cards())))


def deviating_signals(components: dict) -> set[str]:
    """Signal names that fusion counted as deviating, read from flag.components.

    Physiology: |z| >= alert. Mental: direction * z >= alert, or a catalog band alert.
    """
    alert = components.get("alert_robust_z")
    out: set[str] = set()
    for name, c in (components.get("physiology") or {}).items():
        z = c.get("z") if isinstance(c, dict) else None
        if z is not None and alert is not None and abs(z) >= alert:
            out.add(name)
    for name, c in (components.get("mental") or {}).items():
        if not isinstance(c, dict):
            continue
        z, d = c.get("z"), c.get("direction")
        if c.get("band") or (
            z is not None and d in (1, -1) and alert is not None and d * z >= alert
        ):
            out.add(name)
    return out


def choose_cards(state: str, signals: set[str], limit: int = MAX_CARDS) -> list[dict]:
    """Cards whose match.states include ``state`` and whose match.signals are empty
    or overlap ``signals``; ordered by priority (lower first)."""
    chosen = []
    for card in _cards():
        match = card["match"]
        if state not in match["states"]:
            continue
        wanted = set(match["signals"])
        if wanted and not (wanted & signals):
            continue
        chosen.append(card)
    chosen.sort(key=lambda c: c["priority"])
    return json.loads(json.dumps(chosen[:limit]))


def _public(card: dict, signals: set[str]) -> dict:
    return {
        "card_key": card["card_key"],
        "title": card["title"],
        "body": card["body"],
        "contact_support_text": card["contact_support_text"],
        "source_note": card["source_note"],
        "reviewed_by": card["reviewed_by"],
        "matched_signals": sorted(set(card["match"]["signals"]) & signals),
    }


# --------------------------------------------------------------------------- DB-backed


def _models() -> Any:
    import backend.models as m

    return m


def load_guidance_cards(db: Any) -> None:
    """Idempotent upsert of seeds/guidance_cards.json into guidance_cards (by card_key)."""
    from sqlalchemy import select

    m = _models()
    for card in _cards():
        tags = [f"state:{s}" for s in card["match"]["states"]] + [
            f"signal:{s}" for s in card["match"]["signals"]
        ]
        fields = {
            "title": card["title"],
            "body": card["body"],
            "tags": tags,
            "source_note": card["source_note"],
            "reviewed_by": card["reviewed_by"],
        }
        row = db.scalars(
            select(m.GuidanceCard).where(m.GuidanceCard.card_key == card["card_key"])
        ).first()
        if row is None:
            db.add(m.GuidanceCard(card_key=card["card_key"], **fields))
        else:
            for k, v in fields.items():
                setattr(row, k, v)
    db.commit()
    log.info("guidance cards loaded: %d", len(_cards()))


def select_guidance(db: Any, user_id: str, flag_id: str) -> list[dict]:
    """Cards for one of the user's flags; records each shown card in guidance_shown.

    Raises UnknownFlag if the flag does not exist or belongs to another user.
    """
    from sqlalchemy import select

    m = _models()
    flag = db.scalars(m.scoped(select(m.Flag).where(m.Flag.id == flag_id), m.Flag, user_id)).first()
    if flag is None:
        raise UnknownFlag(flag_id)
    signals = deviating_signals(flag.components or {})
    cards = choose_cards(flag.state, signals)
    if not cards:
        return []
    keys = [c["card_key"] for c in cards]
    rows = {
        r.card_key: r
        for r in db.scalars(select(m.GuidanceCard).where(m.GuidanceCard.card_key.in_(keys)))
    }
    # guidance_shown: at most one row per (user, flag, card) per UTC day.
    day_start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    already = set(
        db.scalars(
            m.scoped(
                select(m.GuidanceShown.card_id).where(
                    m.GuidanceShown.flag_id == flag.id, m.GuidanceShown.shown_at >= day_start
                ),
                m.GuidanceShown,
                user_id,
            )
        )
    )
    out = []
    for card in cards:
        row = rows.get(card["card_key"])
        if row is None:  # catalog not loaded: still show the card, nothing to link
            log.warning("guidance card %s not in DB; run load_guidance_cards", card["card_key"])
        elif row.id not in already:
            db.add(m.GuidanceShown(user_id=user_id, card_id=row.id, flag_id=flag.id))
        out.append(_public(card, signals))
    db.commit()
    return out

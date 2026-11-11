"""Guidance cards: seed rules, pure selection, DB selection with user isolation."""

from __future__ import annotations

import json
import re
from datetime import date

import pytest
from sqlalchemy.orm import Session

from backend.db import get_engine
from backend.models import Base, Flag, GuidanceCard, GuidanceShown, User
from backend.services import guidance
from csi_core.config import ROOT

SEED = json.loads((ROOT / "seeds" / "guidance_cards.json").read_text())
STATES = {"phys_only", "mental_only", "both"}  # csi_core.fusion states


# --------------------------------------------------------------------------- seed


def test_five_cards_with_required_fields() -> None:
    cards = SEED["cards"]
    assert len(cards) == 5
    assert {c["card_key"] for c in cards} == {
        "talk_to_support",
        "paced_breathing",
        "caffeine_cutoff",
        "wind_down",
        "schedule_shift",
    }
    for c in cards:
        for f in ("title", "body", "contact_support_text", "source_note"):
            assert isinstance(c[f], str) and c[f].strip(), (c["card_key"], f)
        assert c["reviewed_by"] is None
        assert set(c["match"]["states"]) <= STATES and c["match"]["states"]
        assert isinstance(c["priority"], int)
        assert "flight surgeon" in c["contact_support_text"]


def test_cards_are_conservative() -> None:
    """No diagnoses, conditions, medication or numbers in what the user reads."""
    banned = re.compile(
        r"\b(depress\w*|anxiety disorder|disorder|insomnia|diagnos\w*|medicat\w*|"
        r"pill|dose|dosage|mg|melatonin|you have)\b",
        re.IGNORECASE,
    )
    for c in SEED["cards"]:
        text = " ".join((c["title"], c["body"], c["contact_support_text"]))
        text = text.replace("This is not a diagnosis.", "")
        assert not banned.search(text), c["card_key"]
        assert not re.search(r"\d", c["title"] + c["body"]), c["card_key"]


# --------------------------------------------------------------------------- pure


def _comps(phys: dict | None = None, mental: dict | None = None) -> dict:
    return {"physiology": phys or {}, "mental": mental or {}, "alert_robust_z": 2.5}


def test_deviating_signals() -> None:
    comps = _comps(
        phys={"rr_med": {"z": -3.0}, "rr_var": {"z": 1.0}, "restless_frac": {"skipped": "warm_up"}},
        mental={
            "daily_pm.stress": {"z": 3.0, "direction": 1},
            "who5": {"z": 3.0, "direction": -1},  # higher is better: not a deviation
            "phq2": {"band": {"band": "at or above screening cutoff", "source": "catalog"}},
        },
    )
    assert guidance.deviating_signals(comps) == {"rr_med", "daily_pm.stress", "phq2"}


def test_mental_only_always_includes_talk_to_support_first() -> None:
    cards = guidance.choose_cards("mental_only", {"phq2"})
    assert cards[0]["card_key"] == "talk_to_support"
    assert all("mental_only" in c["match"]["states"] for c in cards)


def test_phys_only_never_shows_support_card_without_mental_signal() -> None:
    keys = [c["card_key"] for c in guidance.choose_cards("phys_only", {"restless_frac"})]
    assert "talk_to_support" not in keys
    assert keys == ["caffeine_cutoff", "wind_down"]


def test_signal_gating_and_limit() -> None:
    assert guidance.choose_cards("phys_only", set()) == []
    many = {"rr_med", "restless_frac", "presence_hours", "daily_pm.stress"}
    cards = guidance.choose_cards("both", many)
    assert len(cards) == guidance.MAX_CARDS
    assert [c["priority"] for c in cards] == sorted(c["priority"] for c in cards)


# --------------------------------------------------------------------------- DB


@pytest.fixture()
def db():
    engine = get_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all(User(id=u, email=f"{u}@example.test", is_synthetic=True) for u in ("ua", "ub"))
        s.flush()
        guidance.load_guidance_cards(s)
        yield s
    engine.dispose()


def _flag(db, user: str, state: str, comps: dict) -> str:
    f = Flag(
        user_id=user,
        date=date(2026, 11, 10),
        domain_pair="physiology|mental",
        phys_level=int(state != "mental_only"),
        mental_level=int(state != "phys_only"),
        state=state,
        priority=1.0,
        components=comps,
        message_key=f"flag.{state}",
    )
    db.add(f)
    db.commit()
    return f.id


def test_load_cards_idempotent(db) -> None:
    guidance.load_guidance_cards(db)
    assert db.query(GuidanceCard).count() == 5
    row = db.query(GuidanceCard).filter_by(card_key="talk_to_support").one()
    assert row.reviewed_by is None and "state:mental_only" in row.tags


def test_select_guidance_records_shown(db) -> None:
    fid = _flag(
        db,
        "ua",
        "both",
        _comps(
            phys={"restless_frac": {"z": 3.1}},
            mental={"daily_pm.stress": {"z": 2.6, "direction": 1}},
        ),
    )
    cards = guidance.select_guidance(db, "ua", fid)
    keys = [c["card_key"] for c in cards]
    assert keys[0] == "talk_to_support" and len(keys) <= guidance.MAX_CARDS
    assert all(c["contact_support_text"] and c["reviewed_by"] is None for c in cards)
    shown = db.query(GuidanceShown).all()
    assert len(shown) == len(cards)
    assert {s.user_id for s in shown} == {"ua"} and {s.flag_id for s in shown} == {fid}


def test_select_guidance_user_isolation(db) -> None:
    """User A cannot get guidance for (or learn about) user B's flag."""
    fid = _flag(db, "ub", "mental_only", _comps(mental={"phq2": {"band": {"band": "x"}}}))
    with pytest.raises(guidance.UnknownFlag):
        guidance.select_guidance(db, "ua", fid)
    assert db.query(GuidanceShown).count() == 0
    assert guidance.select_guidance(db, "ub", fid)


def test_select_guidance_unknown_flag(db) -> None:
    with pytest.raises(guidance.UnknownFlag):
        guidance.select_guidance(db, "ua", "nope")

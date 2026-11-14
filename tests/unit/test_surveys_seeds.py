"""Seed instrument JSON follows the schema in docs/interfaces.md."""

import json
from pathlib import Path

import pytest

SEEDS = Path(__file__).resolve().parents[2] / "seeds" / "instruments"
EXPECTED = {"phq2", "gad2", "who5", "phq9", "daily_am", "daily_pm", "mini_ipip", "psyche60"}


def _load(name: str) -> dict:
    return json.loads((SEEDS / f"{name}.json").read_text())


def test_all_instruments_present() -> None:
    assert {p.stem for p in SEEDS.glob("*.json")} == EXPECTED


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_schema(name: str) -> None:
    d = _load(name)
    assert d["id"] == name
    for field in ("name", "version", "timeframe", "license_note"):
        assert isinstance(d[field], str) and d[field]
    assert "source_url" in d
    keys = [it["key"] for it in d["items"]]
    assert len(keys) == len(set(keys)) and keys
    for it in d["items"]:
        assert it["text"]
        values = [o["value"] for o in it["options"]]
        assert values and all(isinstance(v, int) for v in values)
        assert len(values) == len(set(values))
    sc = d["scoring"]
    assert sc["method"] in {"sum", "sum_x4"}
    # Bands must cite a source or be marked placeholder; never invented.
    assert sc["ranges_source"]
    if sc["ranges"]:
        assert "PLACEHOLDER" not in sc["ranges_source"]
        prev_max = None
        for r in sc["ranges"]:
            assert r["min"] <= r["max"] and r["label"]
            if prev_max is not None:
                assert r["min"] == prev_max + 1  # contiguous, no gaps or overlap
            prev_max = r["max"]
        assert sc["ranges"][0]["min"] == sc["min"] and prev_max == sc["max"]


def test_published_instruments_cite_source() -> None:
    for name in ("phq2", "gad2", "who5", "phq9"):
        d = _load(name)
        assert d["source_url"].startswith("https://")
        assert d["scoring"]["ranges"], name


def test_phq2_matches_phq9_first_two_items() -> None:
    p2, p9 = _load("phq2"), _load("phq9")
    assert [i["text"] for i in p2["items"]] == [i["text"] for i in p9["items"][:2]]
    assert len(p9["items"]) == 9


def test_alert_flags_only_where_cited() -> None:
    expected_alerts = {
        "phq9": {"moderate", "moderately severe", "severe"},
        "phq2": {"at or above screening cutoff"},
        "gad2": {"at or above screening cutoff"},
        "who5": {"very low wellbeing", "low wellbeing"},
    }
    for name, labels in expected_alerts.items():
        sc = _load(name)["scoring"]
        assert all(isinstance(r["alert"], bool) for r in sc["ranges"])
        assert {r["label"] for r in sc["ranges"] if r["alert"]} == labels
        assert "Alert basis" in sc["ranges_source"]


def test_direction() -> None:
    assert {n: _load(n)["direction"] for n in ("phq9", "phq2", "gad2", "who5")} == {
        "phq9": 1,
        "phq2": 1,
        "gad2": 1,
        "who5": -1,
    }
    for n in ("daily_am", "daily_pm"):
        d = _load(n)
        assert d["direction"] is None
        dirs = {it["key"]: it["direction"] for it in d["items"]}
        assert all(v in (1, -1) for v in dirs.values())
        assert dirs.get("stress", 1) == 1 and dirs.get("mood") == -1

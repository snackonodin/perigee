"""Scoring and answer validation, from the catalog alone (no DB)."""

import pytest

from backend.services import surveys
from backend.services.surveys import InvalidAnswers, score_answers


def _all(inst: dict, value: int) -> dict[str, int]:
    return {it["key"]: value for it in inst["items"]}


def test_phq9_sum_and_band() -> None:
    inst = surveys.get_seed_instrument("phq9")
    r = score_answers(inst, _all(inst, 3))
    assert r["total"] == 27 and r["score"] == 27 and r["band"] == "severe"
    assert r["band_alert"] is True
    r = score_answers(inst, _all(inst, 0))
    assert r["score"] == 0 and r["band"] == "minimal" and r["band_alert"] is False
    answers = _all(inst, 1)  # 9 -> mild
    assert score_answers(inst, answers)["band"] == "mild"
    answers["phq9_1"] = 2  # 10 -> moderate (boundary)
    assert score_answers(inst, answers)["band"] == "moderate"


@pytest.mark.parametrize("name", ["phq2", "gad2"])
def test_two_item_screeners(name: str) -> None:
    inst = surveys.get_seed_instrument(name)
    keys = [it["key"] for it in inst["items"]]
    assert score_answers(inst, {keys[0]: 1, keys[1]: 1})["band"] == "below screening cutoff"
    r = score_answers(inst, {keys[0]: 2, keys[1]: 1})
    assert r["total"] == 3 and r["band"] == "at or above screening cutoff"


def test_who5_times_four() -> None:
    inst = surveys.get_seed_instrument("who5")
    r = score_answers(inst, _all(inst, 5))
    assert r["total"] == 25 and r["score"] == 100 and r["method"] == "sum_x4"
    r = score_answers(inst, _all(inst, 2))  # 10 -> 40
    assert r["score"] == 40 and r["band"] == "low wellbeing"
    r = score_answers(inst, {**_all(inst, 1), "who5_1": 2, "who5_2": 2})  # 7 -> 28
    assert r["score"] == 28 and r["band"] == "very low wellbeing"


def test_daily_checkin_per_item_no_band() -> None:
    inst = surveys.get_seed_instrument("daily_pm")
    r = score_answers(inst, {"mood": 3, "stress": 1, "energy": 2})
    assert r["band"] is None and r["band_alert"] is False
    assert r["items"] == {"mood": 3, "stress": 1, "energy": 2}


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda a: a.pop("phq2_2"), "missing item: phq2_2"),
        (lambda a: a.update(extra=1), "unknown item: extra"),
        (lambda a: a.update(phq2_1=4), "not an allowed option: phq2_1"),
        (lambda a: a.update(phq2_1=-1), "not an allowed option: phq2_1"),
        (lambda a: a.update(phq2_1=True), "not an allowed option: phq2_1"),
    ],
)
def test_validation_errors_name_keys_not_values(mutate, fragment) -> None:
    inst = surveys.get_seed_instrument("phq2")
    answers = {"phq2_1": 1, "phq2_2": 2}
    mutate(answers)
    with pytest.raises(InvalidAnswers) as exc:
        score_answers(inst, answers)
    assert any(fragment in e for e in exc.value.errors)
    assert "4" not in str(exc.value) and "-1" not in " ".join(exc.value.errors)


def test_all_seed_instruments_score_at_min_and_max() -> None:
    for inst in surveys.load_seed_catalog().values():
        lo = {it["key"]: min(o["value"] for o in it["options"]) for it in inst["items"]}
        hi = {it["key"]: max(o["value"] for o in it["options"]) for it in inst["items"]}
        r_lo, r_hi = score_answers(inst, lo), score_answers(inst, hi)
        if inst["scoring"]["ranges"]:
            assert r_lo["band"] is not None and r_hi["band"] is not None
            assert r_lo["score"] == inst["scoring"]["min"]
            assert r_hi["score"] == inst["scoring"]["max"]

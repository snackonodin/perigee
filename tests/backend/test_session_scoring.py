"""Experimental session score: graded, direction-aware ranges (INTEGRATION_PLAN.md D2)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.services import session_scoring as ss
from csi_core.config import RangeCfg, SessionScoringCfg, get_config

CFG = get_config().session_scoring
RR = CFG.respiration_bpm
HR = CFG.heart_rate_bpm


def _still(n: int = 30) -> list[dict]:
    return [{"time_s": float(i), "acceleration_m_s2": 0.01} for i in range(n)]


def _series(values: list[float]) -> list[dict]:
    return [{"time_s": 30.0 * (i + 1), "bpm": v} for i, v in enumerate(values)]


def test_config_section_loads_with_reference_ranges():
    assert CFG is not None
    assert RR.low < RR.high and HR.low < HR.high


def test_inside_range_gets_full_credit():
    for v in (RR.low, (RR.low + RR.high) / 2, RR.high):
        assert ss.grade(v, RR) == ("in", 0.0, 1.0)


def test_credit_falls_with_distance_and_reaches_zero_at_falloff():
    width = RR.high - RR.low
    near = ss.grade(RR.high + 0.1 * width * RR.falloff_high, RR)
    far = ss.grade(RR.high + 0.9 * width * RR.falloff_high, RR)
    gone = ss.grade(RR.high + 2.0 * width * RR.falloff_high, RR)
    assert near[0] == far[0] == gone[0] == "above"
    assert 1.0 > near[2] > far[2] > 0.0
    assert gone[2] == 0.0
    low = ss.grade(RR.low - 0.5 * width * RR.falloff_low, RR)
    assert low[0] == "below" and low[1] < 0 and low[2] == pytest.approx(0.5)


def test_low_and_high_falloffs_are_independent():
    rng = RangeCfg(low=10, high=20, falloff_low=0.1, falloff_high=0.5)
    below = ss.grade(9.5, rng)   # d = 0.05 -> 1 - 0.05/0.1 = 0.5
    above = ss.grade(20.5, rng)  # d = 0.05 -> 1 - 0.05/0.5 = 0.9
    assert below[2] == pytest.approx(0.5) and above[2] == pytest.approx(0.9)


def test_below_and_above_are_counted_and_flagged_separately():
    out = ss.score_session(
        respiration_bpm=_series([RR.low - 2, 16, RR.high + 2]),
        heart_rate_bpm=_series([HR.low - 5]),
        motion_samples=_still(),
    )
    assert out["respiration"]["counts"] == {"below": 1, "in": 1, "above": 1}
    assert out["respiration"]["flag"] == "above_range"  # latest reading
    assert out["heart_rate"]["flag"] == "below_range"
    assert out["respiration"]["mean_deviation_below"] > 0
    assert out["respiration"]["mean_deviation_above"] > 0


def test_score_is_none_until_all_three_inputs_exist():
    for kwargs in (
        {"respiration_bpm": [], "heart_rate_bpm": _series([75]), "motion_samples": _still()},
        {"respiration_bpm": _series([15]), "heart_rate_bpm": None, "motion_samples": _still()},
        {"respiration_bpm": _series([15]), "heart_rate_bpm": _series([75]), "motion_samples": []},
    ):
        out = ss.score_session(**kwargs)
        assert out["sleep_score"] is None and out["score_status"] == "insufficient_inputs"


def test_all_in_range_and_still_scores_100_and_weights_apply():
    out = ss.score_session(
        respiration_bpm=_series([14, 15, 16]),
        heart_rate_bpm=_series([70, 75]),
        motion_samples=_still(),
    )
    assert out["sleep_score"] == 100.0
    half = ss.score_session(
        respiration_bpm=_series([15]),
        heart_rate_bpm=_series([HR.high + 10 * (HR.high - HR.low)]),  # far above: 0 credit
        motion_samples=_still(),
    )
    w = CFG.weights
    assert half["sleep_score"] == pytest.approx(100 * (w.respiration + w.motion), abs=0.1)


def test_further_out_of_range_never_scores_higher():
    scores = [
        ss.score_session(respiration_bpm=_series([RR.high + d]), heart_rate_bpm=_series([75]),
                         motion_samples=_still())["sleep_score"]
        for d in (0, 0.5, 1, 2, 4, 8)
    ]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] > scores[-1]


def test_heart_values_are_reported_unclamped():
    out = ss.score_session(respiration_bpm=_series([15]), heart_rate_bpm=_series([131.0]),
                           motion_samples=_still())
    assert out["heart_rate"]["readings"][0]["value"] == 131.0


def test_unusable_readings_are_dropped():
    out = ss.score_session(
        respiration_bpm=[
            {"time_s": 1, "bpm": None},
            {"time_s": 2, "bpm": "x"},
            {"time_s": 3, "bpm": float("nan")},
        ],
        heart_rate_bpm=_series([75]), motion_samples=_still(),
    )
    assert out["respiration"]["n"] == 0 and out["sleep_score"] is None


def test_weights_must_sum_to_one():
    data = CFG.model_dump()
    data["weights"] = {"respiration": 0.5, "heart_rate": 0.5, "motion": 0.5}
    with pytest.raises(ValidationError):
        SessionScoringCfg.model_validate(data)


def test_session_score_never_reaches_the_nightly_context_engine():
    src = Path(ss.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(m.endswith("engine.api") or m.endswith("context_engine") for m in imported)
    ce = Path(ss.__file__).with_name("context_engine.py").read_text(encoding="utf-8")
    assert "session_scoring" not in ce and "sleep_scorer" not in ce

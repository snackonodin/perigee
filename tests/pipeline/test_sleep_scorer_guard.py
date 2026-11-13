"""Guard the experimental CSI sleep score away from the clinical Context Engine.

``waiwai1.engine.sleep_scorer.score_sleep_session`` is an app-facing display
metric. Its output must never be consumed by ``waiwai1.engine.api.run`` or leak
into the returned state.
"""

from __future__ import annotations

import inspect

import pytest

from waiwai1.engine import api as engine_api
from waiwai1.engine.api import run
from waiwai1.engine.sleep_scorer import score_sleep_session

SCORER_KEYS = frozenset(
    {
        "sleep_score",
        "score_status",
        "score_components",
        "normal_ranges",
        "dashboard",
        "motion",
        "limitations",
    }
)


def engine_payload() -> dict:
    return {
        "persona": {
            "user_id": "scorer-guard",
            "baselines": {"rr_med": 14.0, "mad_rr": 0.55},
        },
        "sensing_data": {"rr_med": 14.0, "quality": 0.9, "valid_hours": 7},
        "clinical_scales": {"phq9_item9": 0},
    }


def scorer_inputs() -> dict:
    return {
        "respiration_bpm": [{"time_s": t, "bpm": 15.0} for t in (0.0, 30.0, 60.0)],
        "heart_rate_samples": [
            {"time_s": 0.0, "bpm": 72.0},
            {"time_s": 10.0, "bpm": 84.0},
            {"time_s": 20.0, "bpm": 120.0},
        ],
        "motion_samples": [{"time_s": float(t), "acceleration_m_s2": 0.01} for t in range(4)],
    }


def _all_keys(value) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys |= _all_keys(child)
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys |= _all_keys(child)
        return keys
    return set()


def test_scorer_output_is_ignored_and_never_enters_returned_state():
    baseline = run(engine_payload())

    payload = engine_payload()
    payload["sensing_data"]["sleep_scorer"] = score_sleep_session(**scorer_inputs())
    with_scorer = run(payload)

    assert with_scorer == baseline
    assert _all_keys(with_scorer).isdisjoint(SCORER_KEYS)
    assert _all_keys(with_scorer["state"]).isdisjoint(SCORER_KEYS)


def test_engine_api_does_not_wire_the_sleep_scorer():
    source = inspect.getsource(engine_api)
    assert "sleep_scorer" not in source
    assert "score_sleep_session" not in source


@pytest.mark.parametrize("missing", ["respiration_bpm", "heart_rate_samples", "motion_samples"])
def test_missing_inputs_report_insufficient_inputs(missing):
    inputs = scorer_inputs()
    inputs[missing] = []

    result = score_sleep_session(**inputs)

    assert result["sleep_score"] is None
    assert result["score_status"] == "insufficient_inputs"


@pytest.mark.parametrize("bpm", [120.0, 45.0])
def test_heart_rate_outside_display_reference_is_not_clamped(bpm):
    inputs = scorer_inputs()
    inputs["heart_rate_samples"] = [
        {"time_s": 0.0, "bpm": 72.0},
        {"time_s": 30.0, "bpm": bpm},
    ]

    result = score_sleep_session(**inputs)

    assert result["dashboard"]["heart_rate_15s_high_bpm"] == bpm
    assert result["dashboard"]["heart_rate_display_reference_bpm"] == [80.0, 90.0]
    assert result["normal_ranges"]["heart_rate_bpm"] == [65.0, 90.0]

"""Non-tunable Context Engine crisis invariants."""

from __future__ import annotations

import pytest

from waiwai1.engine.api import run


def payload(item9=0):
    return {
        "persona": {"user_id": "safety-test", "baselines": {"rr_med": 14.0, "mad_rr": 0.55}},
        "sensing_data": {"rr_med": 14.0, "quality": 0.9, "valid_hours": 7},
        "clinical_scales": {"phq9": 1, "gad7": 1, "who5": 90, "k6": 1, "phq9_item9": item9},
    }


@pytest.mark.parametrize("item9", [None, "invalid", "1", 1, 2, 3])
def test_crisis_item9_fails_closed_before_routine_output(item9):
    result = run(payload(item9))
    assert result["safety_status"]["crisis_override_triggered"] is True
    assert result["safety_status"]["escalation_type"] not in (None, "NONE")
    assert set(result) == {"safety_status", "state"}


def test_missing_crisis_item_fails_closed():
    data = payload()
    del data["clinical_scales"]["phq9_item9"]
    result = run(data)
    assert result["safety_status"]["crisis_override_triggered"] is True
    assert set(result) == {"safety_status", "state"}

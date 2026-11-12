"""State-carrying Context Engine invariants; these do not modify engine behavior."""

from __future__ import annotations

import json

import pytest

from waiwai1.engine.api import run


def payload(rr=14.0, state=None):
    data = {
        "persona": {"user_id": "state-test", "baselines": {"rr_med": 14.0, "mad_rr": 0.55}},
        "sensing_data": {"rr_med": rr, "quality": 0.9, "valid_hours": 7},
        "clinical_scales": {"phq9_item9": 0},
    }
    if state is not None:
        data["state"] = state
    return data


def test_same_payload_and_reloaded_state_are_deterministic():
    first = run(payload())
    carried = json.loads(json.dumps(first["state"], sort_keys=True))
    next_payload = payload(14.2, carried)
    assert run(next_payload) == run(next_payload)


def test_state_has_schema_version():
    result = run(payload())
    assert result["state"].get("schema_version") is not None


def test_history_is_capped_and_cold_start_uses_supplied_baseline():
    old = {"baseline_rr": [14.0] * 27, "history": [0.1] * 40, "cusum_s_t": 0}
    result = run(payload(14.2, old))
    assert len(result["state"]["baseline_rr"]) <= 28
    assert len(result["state"]["history"]) <= 28
    expected = round((14.2 - 14.0) / (1.4826 * 0.55), 4)
    assert result["scores_and_metrics"]["phys_z_raw"] == expected


def test_alert_night_does_not_enter_baseline_history():
    old = {"baseline_rr": [14.0] * 10, "history": [], "cusum_s_t": 0}
    result = run(payload(14.0 + 4 * 1.4826 * 0.55, old))
    assert len(result["state"]["baseline_rr"]) == 10

"""Safety item gaps and malformed values must fail closed at the backend boundary."""

from __future__ import annotations

import pytest

from backend.services import surveys


@pytest.mark.parametrize("answer", [{"phq9_9": None}, {"phq9_9": "bad"}, {"phq9_9": "1"}])
def test_phq9_item9_unparseable_fails_closed(answer):
    result = surveys.safety_check(surveys.get_seed_instrument("phq9"), answer)
    assert result.show is True


def test_phq9_item9_missing_fails_closed():
    # 2026-11-13 contract: a missing item 9 is reported separately and still requires
    # the safety screen (safety_screen_required), without counting as a positive answer.
    inst = surveys.get_seed_instrument("phq9")
    assert surveys.missing_safety_items(inst, {}) == ["phq9_9"]
    assert (
        surveys.safety_fields(surveys.safety_check(inst, {}), ["phq9_9"])["safety_screen_required"]
        is True
    )

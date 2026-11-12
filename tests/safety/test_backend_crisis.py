"""Safety item gaps and malformed values must fail closed at the backend boundary."""

from __future__ import annotations

import pytest

from backend.services import surveys


@pytest.mark.parametrize("answer", [{}, {"phq9_9": None}, {"phq9_9": "bad"}, {"phq9_9": "1"}])
def test_phq9_item9_missing_or_unparseable_fails_closed(answer):
    result = surveys.safety_check(surveys.get_seed_instrument("phq9"), answer)
    assert result.show is True


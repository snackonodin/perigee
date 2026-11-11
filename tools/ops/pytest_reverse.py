"""pytest plugin: run the collected tests in reverse order.

Used by tools/ops/stress.sh to catch order dependence that random shuffling may miss
(e.g. a test that only passes because another one ran before it).
Load with:  python -m pytest -p no:randomly -p tools.ops.pytest_reverse
"""

from __future__ import annotations

import pytest


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session, config, items) -> None:  # noqa: ARG001
    items.reverse()

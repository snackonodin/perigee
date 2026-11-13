"""Adapter: the team's I/Q Doppler movement analysis -> acceleration samples.

Calls the vendored, unmodified ``plugins/vendor/waiwai1/movement.py``. That file imports
``heart_rate`` as a top-level module, so we alias the vendored ``heart_rate`` under that name
before importing it (no edits to vendored code). Needs a signed I/Q team-format capture.

    samples = acceleration_samples(Path("capture.csv"), start_host_time_s=61.0)
    # -> [{"time_s": 2.0, "acceleration_m_s2": 0.03}, ...] on the run's own clock
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _movement():
    from plugins.vendor.waiwai1 import heart_rate

    sys.modules.setdefault("heart_rate", heart_rate)
    from plugins.vendor.waiwai1 import movement

    return movement


def acceleration_samples(
    path: Path, start_host_time_s: float | None = None
) -> list[dict[str, Any]]:
    """Per-window acceleration on the capture's clock (from ``start_host_time_s``).

    Returns [] when the capture cannot support Doppler (no I/Q, too few clean windows).
    """
    try:
        result = _movement().analyze_capture(path, start_host_time_s=start_host_time_s)
    except (ValueError, FileNotFoundError):
        return []
    return [
        {"time_s": float(w["center_s"]), "acceleration_m_s2": float(w["acceleration_m_s2"])}
        for w in result.get("windows", [])
        if w.get("acceleration_m_s2") is not None
    ]

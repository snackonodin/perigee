"""Team amplitude motion feature (waiwai1 pipeline.py motion_feature) as a plug-in.

Use it with config.yaml:
    estimators:
      motion: "plugins.team_motion:motion_core_matrix"
      motion_input: matrix

The score is the team's maximum 0.8-3 Hz residual power over 2-s subwindows after
removing breathing harmonics (higher = more movement). The team's own motion
threshold is uncalibrated (config.json: null), so the core never asserts motion by
itself; csi_core flags windows whose score is a session-level robust outlier.
The team's Doppler movement analysis (movement.py) needs I/Q captures (SCR-2).
"""

from __future__ import annotations

import numpy as np

from plugins.vendor.waiwai1 import pipeline as wp


def motion_core_matrix(
    amps: np.ndarray, active: np.ndarray, fs: float, cfg, rr_hint: float | None
) -> tuple[bool, float]:
    return False, float(wp.motion_feature(amps[:, active], fs, rr_hint))

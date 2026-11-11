"""Team heart-rate pipeline (waiwai1 heart_rate.py) placeholder plug-in.

The team's method needs signed I/Q CSI (ESP-B firmware). csi_core's clean signal
and the current team captures are amplitude-only, so this core returns no estimate
(hr None, quality 0) rather than a number the team method cannot support. The I/Q
reader and the real wrapper come with SCR-2, once an I/Q capture exists.
"""

from __future__ import annotations

import numpy as np


def heart_core(x: np.ndarray, fs: float, cfg) -> tuple[float | None, float]:
    return None, 0.0

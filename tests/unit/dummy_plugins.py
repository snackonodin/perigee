"""Stand-in plug-in cores used to prove the config seam swaps implementations."""

import numpy as np


def breath_core(x: np.ndarray, fs: float, cfg) -> tuple[float | None, float | None, float | None]:
    return 12.0, 12.5, 30.0


def breath_core_disagree(x, fs, cfg):
    return 12.0, 20.0, 30.0


def heart_core(x: np.ndarray, fs: float, cfg) -> tuple[float | None, float]:
    return 61.0, 0.4


def motion_never(x: np.ndarray, fs: float, cfg) -> tuple[bool, float]:
    return False, 0.0

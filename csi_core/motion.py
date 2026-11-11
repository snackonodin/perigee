"""Motion and presence per analysis window.

Plug-in seam: ``config.yaml estimators.motion`` names a ``motion_core(x, fs, cfg)
-> (motion, score)`` for one window. ``score`` is a per-window motion score where
higher means more movement. csi_core then also flags a window whose score is a
session-level robust outlier (robust z > ``breath.motion_z``), so a core that only
returns a score still works. Presence stays here: window variance at or above
``breath.presence_min_var``.

Reference core: score = log window variance, motion = False. Detection is the
session-level robust z of that score, so a burst raises its window's variance far
above the night's typical level. (A within-window block test was tried and gave
false positives: 1-s blocks of a breathing wave vary too much with phase.)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from csi_core.config import CoreConfig, resolve_estimator

MAD_SCALE = 1.4826  # MAD -> standard deviation for Gaussian data
EPS = 1e-12


@dataclass(frozen=True)
class MotionResult:
    motion: np.ndarray  # bool per window
    presence: np.ndarray  # bool per window
    score: np.ndarray  # core score per window
    z: np.ndarray  # session robust z of score (nan when undefined)


def robust_z_series(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    if v.size == 0:
        return v
    med = np.median(v)
    mad = np.median(np.abs(v - med)) * MAD_SCALE
    if not np.isfinite(mad) or mad <= 0:
        return np.full(v.shape, np.nan)
    return (v - med) / mad


def reference_core(x: np.ndarray, fs: float, cfg: CoreConfig) -> tuple[bool, float]:
    x = np.asarray(x, dtype=float)
    return False, float(np.log(np.var(x) + EPS)) if x.size else float(np.log(EPS))


def detect(windows: list[np.ndarray], fs: float, cfg: CoreConfig) -> MotionResult:
    """Run the configured motion core per window, then the session-level check."""
    core = resolve_estimator(cfg.estimators.motion)
    res = [core(w, fs, cfg) for w in windows]
    core_motion = np.array([bool(m) for m, _ in res], dtype=bool)
    score = np.array([float(s) for _, s in res], dtype=float)
    z = robust_z_series(score)
    motion = core_motion | (np.nan_to_num(z, nan=0.0) > cfg.breath.motion_z)
    var = np.array([float(np.var(w)) if w.size else 0.0 for w in windows])
    presence = var >= cfg.breath.presence_min_var
    return MotionResult(motion=motion, presence=presence, score=score, z=z)

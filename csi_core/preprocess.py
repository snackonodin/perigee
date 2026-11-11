"""Raw capture -> one clean, uniformly sampled, band-limited signal.

Reference pipeline: unwrap device time, resample onto a uniform grid, keep the
top-variance subcarriers, Butterworth band-pass (sosfiltfilt), project onto the
first principal component. The internals live in ``reference_project``; to use
another method, pass ``projector=`` to ``clean_band`` (same inputs/outputs).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt

from csi_core.config import CoreConfig
from csi_core.timebase import unwrap_us

MAD_SCALE = 1.4826  # MAD -> standard deviation for Gaussian data

# Seam: (uniform amplitudes [n, n_sub], fs, band_hz, cfg) -> (x [n], notes)
Projector = Callable[
    [np.ndarray, float, tuple[float, float], CoreConfig], tuple[np.ndarray, list[str]]
]


@dataclass(frozen=True)
class CleanSignal:
    t_s: np.ndarray
    x: np.ndarray
    fs: float
    t0_utc: datetime
    quality_notes: list[str] = field(default_factory=list)


def amplitude_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("a") and c[1:].isdigit()]


def resample_uniform(df: pd.DataFrame, cfg: CoreConfig) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Linear-interpolate amplitudes onto a uniform grid on the device timebase."""
    notes: list[str] = []
    t_us = unwrap_us(df["ts_us"].to_numpy(dtype=np.int64), bits=cfg.capture.timestamp_bits)
    t = (t_us - t_us[0]) / 1e6
    order = np.argsort(t, kind="stable")
    if not np.all(order == np.arange(t.size)):
        notes.append("reordered_samples")
    t = t[order]
    amps = df[amplitude_columns(df)].to_numpy(dtype=float)[order]
    t, idx = np.unique(t, return_index=True)
    amps = amps[idx]
    fs = float(cfg.preprocess.resample_hz)
    grid = np.arange(0.0, t[-1], 1.0 / fs) if t[-1] > 0 else np.zeros(1)
    out = np.column_stack([np.interp(grid, t, amps[:, k]) for k in range(amps.shape[1])])
    # A gap is a missing sample: over the capture threshold and over two typical periods.
    gaps = np.diff(t)
    limit = max(cfg.capture.gap_threshold_s, 2 * float(np.median(gaps))) if gaps.size else 0.0
    n_gaps = int((gaps > limit).sum())
    if n_gaps:
        notes.append(f"interpolated_gaps={n_gaps}")
    return grid, out, notes


def bandpass(a: np.ndarray, fs: float, band_hz: tuple[float, float], order: int) -> np.ndarray:
    sos = butter(order, band_hz, btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, a, axis=0)


def calm_mask(y: np.ndarray, fs: float, z_max: float) -> np.ndarray:
    """Samples in 1-s blocks whose energy is not a robust outlier (motion excluded)."""
    blk = max(int(fs), 1)
    nb = y.shape[0] // blk
    mask = np.ones(y.shape[0], dtype=bool)
    if nb < 3:
        return mask
    e = np.log(np.var(y[: nb * blk].reshape(nb, blk, -1), axis=1).sum(axis=1) + 1e-12)
    med = np.median(e)
    mad = np.median(np.abs(e - med)) * MAD_SCALE
    if mad <= 0:
        return mask
    bad = (e - med) / mad > z_max
    mask[: nb * blk] = ~np.repeat(bad, blk)
    return mask


def reference_project(
    amps: np.ndarray, fs: float, band_hz: tuple[float, float], cfg: CoreConfig
) -> tuple[np.ndarray, list[str]]:
    """Reference: band-pass, keep top-variance subcarriers, first principal component.

    PCA weights are fitted on calm samples only (motion bursts would otherwise
    dominate the component), then applied to every sample.
    """
    notes: list[str] = []
    y = bandpass(amps, fs, band_hz, cfg.preprocess.butter_order)
    var = y.var(axis=0)
    k = min(cfg.preprocess.n_subcarriers_keep, y.shape[1])
    keep = np.argsort(var)[::-1][:k]
    y = y[:, keep] - y[:, keep].mean(axis=0)
    calm = calm_mask(y, fs, cfg.breath.motion_z)
    if calm.mean() < 0.5:
        notes.append("pca_fit_on_all_samples")
        calm[:] = True
    _, _, vt = np.linalg.svd(y[calm], full_matrices=False)
    w = vt[: cfg.preprocess.pca_components].T
    x = (y @ w)[:, 0]
    return x, notes


def clean_band(
    df: pd.DataFrame,
    cfg: CoreConfig,
    band_hz: tuple[float, float],
    *,
    projector: Projector | None = None,
) -> CleanSignal:
    """Clean signal for any band (breathing, heart). ``projector`` is the seam."""
    if len(df) < 2:
        raise ValueError("not enough rows to clean")
    t, amps, notes = resample_uniform(df, cfg)
    fs = float(cfg.preprocess.resample_hz)
    min_len = 3 * (2 * cfg.preprocess.butter_order + 1) * 3
    if t.size < min_len:
        raise ValueError("capture too short to filter")
    x, more = (projector or reference_project)(amps, fs, tuple(band_hz), cfg)
    t0 = pd.Timestamp(df["host_time_utc"].iloc[0]).to_pydatetime()
    return CleanSignal(
        t_s=t, x=np.asarray(x, dtype=float), fs=fs, t0_utc=t0, quality_notes=notes + list(more)
    )


def clean(df: pd.DataFrame, cfg: CoreConfig) -> CleanSignal:
    """Breathing-band clean signal (interfaces.md)."""
    return clean_band(df, cfg, cfg.preprocess.breath_band_hz)

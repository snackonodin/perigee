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
    # Only when a core takes matrix input: bin-averaged amplitudes on the same
    # grid as x (rows aligned with t_s) and the active-subcarrier mask.
    amps: np.ndarray | None = None
    active: np.ndarray | None = None


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


def bin_average(df: pd.DataFrame, cfg: CoreConfig) -> tuple[np.ndarray, np.ndarray]:
    """(n, n_sub) amplitudes averaged in 1/fs bins of device time, plus active mask.

    Same steps as the team's resample_packets: drop non-increasing device
    timestamps, divide each packet by its mean over active subcarriers, average
    per bin, linearly interpolate empty bins. Bin 0 starts at the first packet.
    """
    fs = float(cfg.preprocess.resample_hz)
    t_us = unwrap_us(df["ts_us"].to_numpy(dtype=np.int64), bits=cfg.capture.timestamp_bits)
    amps = df[amplitude_columns(df)].to_numpy(dtype=float)
    keep = np.ones(t_us.size, dtype=bool)
    last = t_us[0]
    for i in range(1, t_us.size):  # strictly increasing against the last kept packet
        if t_us[i] <= last:
            keep[i] = False
        else:
            last = t_us[i]
    t = (t_us[keep] - t_us[keep][0]) / 1e6
    amps = amps[keep]
    active = (amps > 0).mean(axis=0) >= 0.99
    row_mean = amps[:, active].mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        norm = np.where(row_mean[:, None] > 0, amps / row_mean[:, None], 0.0)
    n = int(np.floor(t[-1] * fs)) + 1
    idx = np.floor(t * fs).astype(int)
    totals = np.zeros((n, amps.shape[1]))
    counts = np.zeros(n, dtype=int)
    np.add.at(totals, idx, norm)
    np.add.at(counts, idx, 1)
    observed = np.flatnonzero(counts > 0)
    out = np.zeros_like(totals)
    out[observed] = totals[observed] / counts[observed, None]
    grid = np.arange(n)
    for k in range(amps.shape[1]):
        out[:, k] = np.interp(grid, observed, out[observed, k])
    return out, active


IQ_MIN_INTERVAL_US = 2000  # the team's I/Q loader rejects packets < 2 ms apart


@dataclass(frozen=True)
class IQPackets:
    """Packet-level complex CSI for phase-based (heart) cores."""

    t_s: np.ndarray  # seconds from the first kept packet (device clock)
    csi: np.ndarray  # complex (n, n_sub)
    active: np.ndarray  # bool (n_sub,)
    t0_utc: datetime


def has_iq(df: pd.DataFrame) -> bool:
    return "i0" in df.columns and "q0" in df.columns


def iq_packets(df: pd.DataFrame, cfg: CoreConfig) -> IQPackets:
    """Same filtering as the team's load_iq_capture: unwrap device time, keep strictly
    increasing packets at least 2 ms apart, active = non-zero in >= 99% of packets."""
    if not has_iq(df):
        raise ValueError("capture has no I/Q columns (amplitude-only firmware)")
    n_sub = sum(1 for c in df.columns if c.startswith("i") and c[1:].isdigit())
    t_us = unwrap_us(df["ts_us"].to_numpy(dtype=np.int64), bits=cfg.capture.timestamp_bits)
    keep = np.zeros(t_us.size, dtype=bool)
    last = None
    for k, t in enumerate(t_us):
        if last is None or (t > last and t - last >= IQ_MIN_INTERVAL_US):
            keep[k] = True
            last = t
    i = df[[f"i{k}" for k in range(n_sub)]].to_numpy(dtype=float)[keep]
    q = df[[f"q{k}" for k in range(n_sub)]].to_numpy(dtype=float)[keep]
    csi = i + 1j * q
    t = (t_us[keep] - t_us[keep][0]) / 1e6
    active = (np.abs(csi) > 0).mean(axis=0) >= 0.99
    t0 = pd.Timestamp(df["host_time_utc"].iloc[int(np.flatnonzero(keep)[0])]).to_pydatetime()
    return IQPackets(t_s=t, csi=csi, active=active, t0_utc=t0)


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
    x = np.asarray(x, dtype=float)
    t0 = pd.Timestamp(df["host_time_utc"].iloc[0]).to_pydatetime()
    mat = active = None
    if "matrix" in (cfg.estimators.breath_input, cfg.estimators.motion_input):
        mat, active = bin_average(df, cfg)
        n = min(mat.shape[0], x.size)  # both grids start at the first packet
        t, x, mat = t[:n], x[:n], mat[:n]
    return CleanSignal(
        t_s=t, x=x, fs=fs, t0_utc=t0, quality_notes=notes + list(more), amps=mat, active=active
    )


def clean(df: pd.DataFrame, cfg: CoreConfig) -> CleanSignal:
    """Breathing-band clean signal (interfaces.md)."""
    return clean_band(df, cfg, cfg.preprocess.breath_band_hz)

"""Read rotating capture files and compute capture-quality stats (FR4)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backend.schemas.contracts import CaptureStats
from csi_core.config import CoreConfig
from csi_core.timebase import count_wraps, unwrap_us

BASE_COLUMNS = ["host_time_utc", "ts_us", "rate"]


def read_rotating(files: list[Path]) -> pd.DataFrame:
    """Concatenate hourly capture files in time order.

    Files are ordered by their first host timestamp (not by name, since names
    repeat across midnight). Row order within a file is kept as captured.
    Returns columns host_time_utc (tz-aware UTC), ts_us (raw int64), rate, a0..aN.
    """
    frames: list[pd.DataFrame] = []
    for p in files:
        df = pd.read_csv(p)
        missing = [c for c in BASE_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"{Path(p).name}: missing columns {missing}")
        df["host_time_utc"] = pd.to_datetime(df["host_time_utc"], utc=True, format="ISO8601")
        frames.append(df)
    if not frames:
        raise ValueError("no capture files")
    amp_cols = [c for c in frames[0].columns if c not in BASE_COLUMNS]
    for p, df in zip(files, frames, strict=True):
        if [c for c in df.columns if c not in BASE_COLUMNS] != amp_cols:
            raise ValueError(f"{Path(p).name}: subcarrier columns differ between files")
    frames = [f for f in frames if len(f)]
    frames.sort(key=lambda f: f["host_time_utc"].iloc[0])
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=BASE_COLUMNS)
    out["ts_us"] = out["ts_us"].astype(np.int64)
    return out[BASE_COLUMNS + amp_cols]


def capture_stats(df: pd.DataFrame, cfg: CoreConfig) -> CaptureStats:
    """Capture-quality numbers on the device timebase (unwrapped ts_us)."""
    rows = int(len(df))
    if rows < 2:
        return CaptureStats(
            rows=rows,
            duration_s=0.0,
            mean_rows_per_s=0.0,
            max_gap_s=0.0,
            gaps_over_50ms=0,
            rate_changes=0,
            timestamp_wraps=0,
        )
    bits = cfg.capture.timestamp_bits
    raw = df["ts_us"].to_numpy(dtype=np.int64)
    t_us = unwrap_us(raw, bits=bits)
    duration_s = float(t_us[-1] - t_us[0]) / 1e6
    gaps_s = np.diff(t_us) / 1e6
    rate = df["rate"].to_numpy()
    return CaptureStats(
        rows=rows,
        duration_s=max(duration_s, 0.0),
        mean_rows_per_s=rows / duration_s if duration_s > 0 else 0.0,
        max_gap_s=max(float(gaps_s.max()), 0.0),
        gaps_over_50ms=int((gaps_s > cfg.capture.gap_threshold_s).sum()),
        rate_changes=int((rate[1:] != rate[:-1]).sum()),
        timestamp_wraps=count_wraps(raw, bits=bits),
    )

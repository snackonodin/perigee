"""Read rotating capture files and compute capture-quality stats (FR4)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.schemas.contracts import CaptureStats
from csi_core.config import CoreConfig
from csi_core.timebase import count_wraps, unwrap_us

BASE_COLUMNS = ["host_time_utc", "ts_us", "rate"]

# Team logger format (features script/waiwai1, logger.py PACKET_FIELDS).
TEAM_REQUIRED = ["ts_us", "mac", "rate", "sig_mode", "len", "host_time_wall_s", "amp_00"]
TEAM_MIN_ACTIVE_FRACTION = 0.99  # a subcarrier is active if non-zero in >= 99% of rows
TEAM_LEN_RANGE = (2, 128)  # CSI payload bytes the team loader accepts


def capture_format(columns: list[str]) -> str:
    """ "synth" (our capture format) or "team" (the team logger), from the header."""
    if all(c in columns for c in BASE_COLUMNS):
        return "synth"
    if all(c in columns for c in TEAM_REQUIRED):
        return "team"
    raise ValueError("unknown capture format: header matches neither synth nor team logger")


def _phone_mac(path: Path) -> str | None:
    """phone_mac from the team's <capture>.json sidecar, if present."""
    meta = path.with_suffix(".json")
    if not meta.is_file():
        return None
    try:
        mac = json.loads(meta.read_text()).get("phone_mac")
    except (OSError, ValueError):
        return None
    return str(mac).strip().lower().replace(":", "") if mac else None


def read_team_capture(path: Path, phone_mac: str | None = None) -> pd.DataFrame:
    """Team logger CSV -> our frame (host_time_utc, ts_us, rate, aK for active K).

    Mirrors the team's load_capture filtering: legacy packets only (sig_mode 0),
    2 <= len <= 128, one phone MAC (sidecar phone_mac, else the most frequent MAC),
    rows ordered by host time. The MAC itself is not returned.
    """
    path = Path(path)
    df = pd.read_csv(path, low_memory=False)
    df = df[(df["sig_mode"] == 0) & df["len"].between(*TEAM_LEN_RANGE)]
    macs = df["mac"].astype(str).str.strip().str.lower().str.replace(":", "", regex=False)
    mac = phone_mac or _phone_mac(path)
    if mac is None and len(macs):
        mac = macs.value_counts().idxmax()
    df = df[macs == mac] if mac is not None else df
    amp = [c for c in df.columns if c.startswith("amp_")]
    active = [c for c in amp if (df[c] > 0).mean() >= TEAM_MIN_ACTIVE_FRACTION]
    order = "host_time_s" if "host_time_s" in df.columns else "host_time_wall_s"
    df = df.sort_values(order, kind="stable")
    out = pd.DataFrame(
        {
            "host_time_utc": pd.to_datetime(
                df["host_time_wall_s"].astype(float), unit="s", utc=True
            ),
            "ts_us": df["ts_us"].astype(np.int64),
            "rate": df["rate"].astype(np.int64),
        }
    )
    for c in active:
        out[f"a{int(c[4:])}"] = df[c].astype(float).to_numpy()
    return out.reset_index(drop=True)


def read_rotating(files: list[Path]) -> pd.DataFrame:
    """Concatenate capture files in time order. The format is detected per file.

    Files are ordered by their first host timestamp (not by name, since names
    repeat across midnight). Row order within a file is kept as captured.
    Returns columns host_time_utc (tz-aware UTC), ts_us (raw int64), rate, a0..aN.
    """
    frames: list[pd.DataFrame] = []
    for p in files:
        header = list(pd.read_csv(p, nrows=0).columns)
        try:
            fmt = capture_format(header)
        except ValueError:
            missing = [c for c in BASE_COLUMNS if c not in header]
            raise ValueError(f"{Path(p).name}: missing columns {missing}") from None
        if fmt == "team":
            frames.append(read_team_capture(Path(p)))
            continue
        df = pd.read_csv(p)
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

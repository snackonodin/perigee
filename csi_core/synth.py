"""Deterministic synthetic night generator in the real capture file format.

Writes hourly ``csi_HH.csv.gz`` files (HH = UTC hour of the first row), plus
``meta.json`` (SessionRecord metadata, no id/user_id) and ``markers.csv``.
Ground truth (motion and absent spans) is written as start/end marker pairs.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

TS_BITS = 32
PHY_RATES = (11, 54)  # PHY rate column values; rare switches exercise rate_changes
DROP_PROB = 0.005  # fraction of packets dropped, to exercise gap stats
JITTER_FRAC = 0.05  # per-packet timing jitter as a fraction of the nominal period
BREATH_AMP = 1.0
NOISE_STD = 0.4
MOTION_AMP = 8.0
MOTION_DUR_S = (5.0, 20.0)
MOTION_BURSTS_PER_H = 0.75  # default density: 6 bursts per 8 h night
BASE_AMP = (10.0, 30.0)


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("start_utc must be timezone-aware")
    return dt.astimezone(UTC)


def _iso(times: pd.DatetimeIndex) -> np.ndarray:
    return times.strftime("%Y-%m-%dT%H:%M:%S.%fZ").to_numpy()


def _rr_series(rr_bpm: float | Callable[[float], float], t_s: np.ndarray) -> np.ndarray:
    if callable(rr_bpm):
        return np.asarray([rr_bpm(float(t)) for t in t_s], dtype=float)
    return np.full_like(t_s, float(rr_bpm), dtype=float)


def _spans_mask(t_s: np.ndarray, spans: list[tuple[float, float]]) -> np.ndarray:
    mask = np.zeros(t_s.shape, dtype=bool)
    for a, b in spans:
        mask |= (t_s >= a) & (t_s < b)
    return mask


def synth_night(
    out_dir: Path,
    *,
    start_utc: datetime,
    hours: float,
    rr_bpm: float | Callable[[float], float],
    fs: float = 100.0,
    n_sub: int = 52,
    motion_bursts: int | None = None,
    absent_spans: list[tuple[float, float]] = (),
    seed: int = 0,
) -> list[Path]:
    """Write a synthetic capture to ``out_dir`` and return the paths written.

    ``rr_bpm`` is a constant or a function of elapsed seconds. ``absent_spans``
    are (start_s, end_s) offsets with nobody in the room (no breathing).
    ``motion_bursts`` defaults to ``MOTION_BURSTS_PER_H * hours`` (rounded), so a
    short capture is not dominated by motion; pass an int to set it exactly.
    """
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = _utc(start_utc)
    duration_s = float(hours) * 3600.0
    n = int(round(duration_s * fs))
    if n < 2:
        raise ValueError("capture too short")

    # Sample times: nominal grid + jitter, with random dropped packets.
    t_s = np.arange(n) / fs + rng.normal(0.0, JITTER_FRAC / fs, n)
    t_s[0] = 0.0
    t_s = np.sort(t_s)
    keep = rng.random(n) >= DROP_PROB
    keep[0] = True
    t_s = t_s[keep]

    # Breathing phase from the (possibly time-varying) rate.
    rr = _rr_series(rr_bpm, t_s)
    phase = 2 * np.pi * np.concatenate([[0.0], np.cumsum(np.diff(t_s) * rr[1:] / 60.0)])
    breath = np.sin(phase)
    absent = _spans_mask(t_s, list(absent_spans))
    breath[absent] = 0.0

    # Motion bursts at random non-overlapping-ish times outside absent spans.
    if motion_bursts is None:
        motion_bursts = int(round(MOTION_BURSTS_PER_H * float(hours)))
    motion_spans: list[tuple[float, float]] = []
    for _ in range(motion_bursts):
        dur = rng.uniform(*MOTION_DUR_S)
        a = rng.uniform(0.0, max(duration_s - dur, 0.0))
        motion_spans.append((a, a + dur))
    motion_spans.sort()
    motion = _spans_mask(t_s, motion_spans) & ~absent

    base = rng.uniform(*BASE_AMP, n_sub)
    gain = rng.uniform(-1.0, 1.0, n_sub)
    amps = base + np.outer(breath * BREATH_AMP, gain) + rng.normal(0, NOISE_STD, (t_s.size, n_sub))
    if motion.any():
        walk = np.cumsum(rng.normal(0, 1.0, (int(motion.sum()), n_sub)), axis=0)
        amps[motion] += MOTION_AMP * walk / np.sqrt(fs)
    amps = np.clip(amps, 0.0, None)

    # Start half a capture before the counter boundary so even short fixtures wrap.
    start_counter = ((1 << TS_BITS) - min(int(duration_s * 1e6 / 2), 1 << TS_BITS)) % (1 << TS_BITS)
    ts_us = (start_counter + np.round(t_s * 1e6).astype(np.int64)) % (1 << TS_BITS)
    rate = np.full(t_s.size, PHY_RATES[0], dtype=np.int64)
    for _ in range(max(1, int(hours))):
        a = int(rng.integers(0, t_s.size))
        rate[a : min(a + int(fs), t_s.size)] = PHY_RATES[1]

    host = pd.DatetimeIndex(t0 + pd.to_timedelta(t_s, unit="s"))
    df = pd.DataFrame({"host_time_utc": _iso(host), "ts_us": ts_us, "rate": rate})
    amp_df = pd.DataFrame(np.round(amps, 3), columns=[f"a{k}" for k in range(n_sub)])
    df = pd.concat([df, amp_df], axis=1)

    written: list[Path] = []
    # Rotate on UTC clock hours, like the real capture.
    hour_key = host.floor("h")
    for h in hour_key.unique():
        chunk = df[hour_key == h]
        p = out_dir / f"csi_{h.hour:02d}.csv.gz"
        chunk.to_csv(p, index=False, compression={"method": "gzip", "mtime": 0})
        written.append(p)

    end = t0 + timedelta(seconds=float(t_s[-1]))
    paced = None if callable(rr_bpm) else float(rr_bpm)
    meta = {
        "start_utc": t0.isoformat().replace("+00:00", "Z"),
        "end_utc": end.isoformat().replace("+00:00", "Z"),
        "condition": "synthetic_night",
        "distance_m": None,
        "posture": None,
        "paced_bpm": paced,
        "reference_device": None,
        "room_notes": f"synth seed={seed} fs={fs} n_sub={n_sub}",
        "phone_model": None,
        "source_kind": "synthetic",
    }
    meta_p = out_dir / "meta.json"
    meta_p.write_text(json.dumps(meta, indent=2, sort_keys=True))
    written.append(meta_p)

    rows: list[tuple[float, str]] = []
    for label, spans in (("motion", motion_spans), ("absent", list(absent_spans))):
        for a, b in spans:
            rows += [(a, f"{label}_start"), (min(b, duration_s), f"{label}_end")]
    rows.sort()
    mk = pd.DataFrame(
        {
            "host_time_utc": _iso(
                pd.DatetimeIndex([t0 + timedelta(seconds=float(s)) for s, _ in rows])
            )
            if rows
            else [],
            "label": [lab for _, lab in rows],
        }
    )
    mk_p = out_dir / "markers.csv"
    mk.to_csv(mk_p, index=False)
    written.append(mk_p)
    return written

"""Device timebase helpers: unwrap the ESP32 free-running microsecond counter."""

from __future__ import annotations

import numpy as np


def _wrap_steps(ts_us: np.ndarray, bits: int) -> np.ndarray:
    """Per-sample wrap flags: a drop larger than half the counter range is a wrap.

    Small backwards steps (jitter, reordered packets) stay well below half the
    range, so they are never counted as wraps.
    """
    period = np.int64(1) << np.int64(bits)
    d = np.diff(ts_us.astype(np.int64))
    return d < -(period // 2)


def count_wraps(ts_us: np.ndarray, bits: int = 32) -> int:
    """Number of counter wraps in a raw timestamp series."""
    ts = np.asarray(ts_us)
    if ts.size < 2:
        return 0
    return int(_wrap_steps(ts, bits).sum())


def unwrap_us(ts_us: np.ndarray, bits: int = 32) -> np.ndarray:
    """Unwrap a raw `bits`-wide µs counter into a continuous int64 µs series.

    Each wrap adds 2**bits to every later sample. Small backwards jitter is kept
    as-is (not a wrap, not clamped), so the output is monotonic up to that jitter.
    """
    ts = np.asarray(ts_us).astype(np.int64)
    if ts.size < 2:
        return ts.copy()
    period = np.int64(1) << np.int64(bits)
    wraps = np.concatenate([[0], np.cumsum(_wrap_steps(ts, bits))]).astype(np.int64)
    return ts + wraps * period

"""Shared windowing helpers for breath and heart estimators."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from csi_core.preprocess import CleanSignal


def window_slices(sig: CleanSignal, window_s: float, step_s: float) -> list[slice]:
    n_win = int(round(window_s * sig.fs))
    n_step = max(int(round(step_s * sig.fs)), 1)
    return [slice(i, i + n_win) for i in range(0, sig.x.size - n_win + 1, n_step)]


def window_times(sig: CleanSignal, s: slice) -> tuple[datetime, datetime]:
    a = sig.t0_utc + timedelta(seconds=float(sig.t_s[s.start]))
    b = sig.t0_utc + timedelta(seconds=float(sig.t_s[s.stop - 1]) + 1.0 / sig.fs)
    return a, b


def spectral_peak(
    x: np.ndarray, fs: float, band_hz: tuple[float, float]
) -> tuple[float | None, float | None]:
    """Welch (one Hann segment, zero-padded) peak in band -> (freq_hz, pnr_db).

    PNR = peak power / median in-band power, in dB. Peak frequency refined by
    parabolic interpolation on the log spectrum.
    """
    from scipy.signal import welch

    if x.size < 8 or not np.any(x):
        return None, None
    nfft = int(2 ** np.ceil(np.log2(x.size * 8)))
    f, p = welch(x - x.mean(), fs=fs, window="hann", nperseg=x.size, nfft=nfft, detrend=False)
    band = (f >= band_hz[0]) & (f <= band_hz[1])
    if band.sum() < 3:
        return None, None
    idx = np.flatnonzero(band)
    i = idx[np.argmax(p[idx])]
    floor = float(np.median(p[idx]))
    if floor <= 0 or p[i] <= 0:
        return None, None
    pnr_db = 10 * np.log10(p[i] / floor)
    fi = f[i]
    if 0 < i < f.size - 1 and p[i - 1] > 0 and p[i + 1] > 0:
        a, b, c = np.log(p[i - 1]), np.log(p[i]), np.log(p[i + 1])
        den = a - 2 * b + c
        if den != 0:
            fi = f[i] + 0.5 * (a - c) / den * (f[1] - f[0])
    return float(fi), float(pnr_db)

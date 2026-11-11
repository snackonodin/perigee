"""Team breathing estimator (waiwai1 pipeline.py) as a csi_core plug-in.

Use it with config.yaml:
    estimators:
      breath: "plugins.team_breath:breath_core_matrix"
      breath_input: matrix

breath_core_matrix runs, per window, exactly the steps of the team's
``score_windows`` (Hampel, 0.05-3 Hz band-pass, top-10 subcarriers by breath-band
SNR, z-score, mean periodogram -> rate A + PNR; filtered peak interval on the best
subcarrier -> rate B), calling the vendored helpers unchanged. The golden test
checks that it reproduces score_windows on a real capture slice.

breath_core (signal input) applies the team's 1-D estimators to csi_core's clean
signal instead; it is a fallback, not the team's full method.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import periodogram

from plugins.vendor.waiwai1 import pipeline as wp

# Band edges of the team's method (pipeline.py score_windows); not app thresholds.
RATE_BAND_HZ = (0.15, 0.5)
NOISE_BAND_HZ = (0.1, 0.7)
PEAK_EXCLUSION_HZ = 0.05
PREFILTER_LOW_HZ = 0.05
PREFILTER_HIGH_HZ = 3.0


def breath_core_matrix(
    amps: np.ndarray, active: np.ndarray, fs: float, cfg
) -> tuple[float | None, float | None, float | None]:
    """One window of bin-averaged amplitudes -> (rate_A, rate_B, pnr_db)."""
    filtered = wp.hampel_filter(amps[:, active], fs)
    filtered = wp._safe_filter(filtered, PREFILTER_LOW_HZ, min(PREFILTER_HIGH_HZ, fs * 0.45), fs)
    selected = filtered[:, wp._rank_subcarriers(filtered, fs, np.ones(filtered.shape[1], bool))]
    std = np.std(selected, axis=0)
    normalized = (selected - np.mean(selected, axis=0)) / np.where(std > 1e-12, std, 1.0)
    freqs, spectra = periodogram(normalized, fs=fs, axis=0, window="hann", scaling="spectrum")
    power = np.mean(spectra, axis=1)
    band = (freqs >= RATE_BAND_HZ[0]) & (freqs <= RATE_BAND_HZ[1])
    candidates = np.flatnonzero(band)
    peak = int(candidates[np.argmax(power[band])])
    noise_mask = (
        (freqs >= NOISE_BAND_HZ[0])
        & (freqs <= NOISE_BAND_HZ[1])
        & (np.abs(freqs - freqs[peak]) > PEAK_EXCLUSION_HZ)
    )
    noise = float(np.median(power[noise_mask])) if np.any(noise_mask) else 0.0
    pnr_db = float(10.0 * np.log10(max(power[peak], 1e-20) / max(noise, 1e-20)))
    freq = float(np.clip(wp._parabolic_peak(freqs, power, peak), *RATE_BAND_HZ))
    _, rate_b = wp._time_domain_peaks(normalized[:, 0], fs)
    return freq * 60.0, rate_b, pnr_db


def breath_core(x: np.ndarray, fs: float, cfg) -> tuple[float | None, float | None, float | None]:
    """Signal-input fallback: the team's spectral (A) and peak-interval (B) estimators."""
    rate_a, pnr_db = wp.spectral_rate(x, fs)
    return rate_a, wp.time_domain_rate(x, fs), pnr_db

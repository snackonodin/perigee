#!/usr/bin/env python3
"""Experimental heart-rate screening from captures containing raw CSI I/Q."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import butter, find_peaks, sosfiltfilt, welch

N_SUBCARRIERS = 64
TIMESTAMP_MODULUS = 2**32
I_FIELDS = [f"csi_i_{index:02d}" for index in range(N_SUBCARRIERS)]
Q_FIELDS = [f"csi_q_{index:02d}" for index in range(N_SUBCARRIERS)]


def load_iq_capture(path: str | Path, start_host_time_s: float | None = None):
    """Load signed I/Q columns, unwrap device timestamps, and reject sub-2ms rows."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Capture CSV does not exist: {path}")

    records: list[tuple[int, float, int, int, np.ndarray]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"ts_us", "host_time_s", "len", "rssi", "rate", "sig_mode", *I_FIELDS, *Q_FIELDS}
        missing = required.difference(reader.fieldnames or ())
        if missing:
            if missing.intersection((*I_FIELDS, *Q_FIELDS)):
                raise ValueError(
                    f"{path} has no raw CSI I/Q columns; it is a magnitude-only capture. "
                    "Flash ESP-B with signed-I/Q firmware and record new data."
                )
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            try:
                host_time = float(row["host_time_s"])
                if start_host_time_s is not None and host_time < start_host_time_s:
                    continue
                ts = int(row["ts_us"])
                length = int(row["len"])
                rssi = int(row["rssi"])
                rate = int(row["rate"])
                sig_mode = int(row["sig_mode"])
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"Invalid I/Q packet on CSV row {line_number}: {exc}") from exc
            if not 0 <= ts < TIMESTAMP_MODULUS:
                raise ValueError(f"Timestamp out of uint32 range on CSV row {line_number}")
            if length < 2 or length > 128 or sig_mode != 0:
                continue
            count = min(length // 2, N_SUBCARRIERS)
            if any(row[field] == "" for field in (*I_FIELDS[:count], *Q_FIELDS[:count])):
                raise ValueError(
                    f"Capture has magnitude-only rows; flash ESP-B firmware with signed I/Q "
                    f"(row {line_number})"
                )
            try:
                i_values = [float(row[field]) for field in I_FIELDS[:count]]
                q_values = [float(row[field]) for field in Q_FIELDS[:count]]
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"Invalid I/Q values on CSV row {line_number}: {exc}") from exc
            if not np.isfinite(host_time) or not np.isfinite(i_values).all() or not np.isfinite(q_values).all():
                raise ValueError(f"Non-finite I/Q packet data on CSV row {line_number}")
            iq = np.zeros(N_SUBCARRIERS, dtype=np.complex128)
            iq[:count] = np.asarray(i_values) + 1j * np.asarray(q_values)
            records.append((ts, host_time, rssi, rate, iq))

    if len(records) < 2:
        raise ValueError("Fewer than two matching I/Q packets were found after the selected start time")
    records.sort(key=lambda item: item[1])

    timestamps: list[float] = []
    kept: list[tuple[int, float, int, int, np.ndarray]] = []
    wrap_offset = 0
    previous_raw = records[0][0]
    previous_unwrapped = previous_raw
    for index, record in enumerate(records):
        raw_ts = record[0]
        if index and raw_ts < previous_raw and previous_raw - raw_ts > TIMESTAMP_MODULUS // 2:
            wrap_offset += TIMESTAMP_MODULUS
        unwrapped = raw_ts + wrap_offset
        previous_raw = raw_ts
        if kept and unwrapped <= previous_unwrapped:
            continue
        if kept and unwrapped - previous_unwrapped < 2000:
            continue
        kept.append(record)
        timestamps.append(unwrapped / 1_000_000.0)
        previous_unwrapped = unwrapped
    if len(kept) < 2:
        raise ValueError("Fewer than two increasing I/Q timestamps remain after filtering")

    times = np.asarray(timestamps, dtype=float)
    times -= times[0]
    vectors = np.asarray([record[4] for record in kept])
    mask = np.mean(np.abs(vectors) > 0, axis=0) >= 0.99
    if np.count_nonzero(mask) < 8:
        raise ValueError("Fewer than eight consistently non-zero subcarriers were found")
    return times, vectors, mask, np.asarray([record[2] for record in kept]), np.asarray(
        [record[3] for record in kept]
    )


def sanitize_phase(csi: np.ndarray, active_mask: np.ndarray) -> np.ndarray:
    """Remove per-packet phase intercept and linear subcarrier slope by least squares."""
    active_indices = np.flatnonzero(active_mask)
    if active_indices.size < 8:
        raise ValueError("At least eight active subcarriers are required for phase sanitization")
    sanitized = np.zeros_like(csi, dtype=np.complex128)
    design = np.column_stack((np.ones(active_indices.size), active_indices))
    for row_index, row in enumerate(csi):
        values = row[active_indices]
        phase = np.unwrap(np.angle(values))
        coefficients, *_ = np.linalg.lstsq(design, phase, rcond=None)
        corrected_phase = phase - design @ coefficients
        sanitized[row_index, active_indices] = np.abs(values) * np.exp(1j * corrected_phase)
    return sanitized


def _hampel(values: np.ndarray, fs: float) -> np.ndarray:
    size = max(3, int(round(0.25 * fs)) | 1)
    median = median_filter(values, size=size, mode="nearest")
    deviation = median_filter(np.abs(values - median), size=size, mode="nearest")
    threshold = 3.0 * 1.4826 * deviation
    result = values.copy()
    outliers = (threshold > 0) & (np.abs(values - median) > threshold)
    result[outliers] = median[outliers]
    return result


def analyze_window(times: np.ndarray, csi: np.ndarray, active_mask: np.ndarray) -> dict:
    duration = float(times[-1] - times[0])
    if duration < 12:
        raise ValueError("Heart-rate windows must contain at least 12 seconds of data")
    median_dt = float(np.median(np.diff(times)))
    fs = min(100.0, 1.0 / median_dt)
    if fs <= 5.0:
        raise ValueError(f"Insufficient packet rate for cardiac analysis: {fs:.2f} Hz")
    clean = sanitize_phase(csi, active_mask)
    delay = np.fft.fftshift(np.fft.ifft(clean, axis=1), axes=1)
    uniform_time = np.arange(times[0], times[-1], 1.0 / fs)
    delay_phase = np.unwrap(np.angle(delay), axis=0)
    phase_series = np.column_stack([
        np.interp(uniform_time, times, delay_phase[:, index])
        for index in range(N_SUBCARRIERS)
    ])
    phase_series -= np.mean(phase_series, axis=0, keepdims=True)

    low, high = 0.8, 2.5
    if high >= fs / 2:
        raise ValueError(f"Packet rate {fs:.2f} Hz is too low for the 2.5 Hz cardiac passband")
    sos = butter(3, [low, high], btype="bandpass", fs=fs, output="sos")
    candidate_signals = []
    candidate_psds = []
    frequency = None
    for bin_index in range(N_SUBCARRIERS):
        conditioned = _hampel(phase_series[:, bin_index], fs)
        filtered = sosfiltfilt(sos, conditioned)
        current_frequency, psd = welch(filtered, fs=fs, nperseg=min(len(filtered), int(fs * 8)))
        band = (current_frequency >= low) & (current_frequency <= high)
        if not np.any(band):
            continue
        candidate_signals.append(filtered)
        candidate_psds.append((current_frequency, psd, band))
        frequency = current_frequency
    if not candidate_psds:
        raise ValueError("No delay-bin spectrum covers the cardiac frequency band")

    scores = [float(np.sum(psd[band])) for _, psd, band in candidate_psds]
    best_index = int(np.argmax(scores))
    frequency, psd, band = candidate_psds[best_index]
    cardiac_frequencies = frequency[band]
    peak_frequency = float(cardiac_frequencies[int(np.argmax(psd[band]))])
    signal = candidate_signals[best_index]
    minimum_distance = max(1, int(fs * 60.0 / 150.0))
    prominence = max(float(np.std(signal) * 0.35), np.finfo(float).eps)
    peaks, _ = find_peaks(signal, distance=minimum_distance, prominence=prominence)
    peak_times = uniform_time[peaks]
    ibi = np.diff(peak_times)
    plausible_ibi = ibi[(ibi >= 60.0 / 150.0) & (ibi <= 60.0 / 48.0)]
    peak_rate = float(60.0 / np.median(plausible_ibi)) if plausible_ibi.size >= 2 else None
    floor = max(float(np.median(psd[band])), np.finfo(float).tiny)
    peak_power = max(float(np.max(psd[band])), np.finfo(float).tiny)
    pnr_db = float(10.0 * np.log10(peak_power / floor))
    return {
        "duration_s": duration,
        "sample_rate_hz": fs,
        "active_subcarriers": int(np.count_nonzero(active_mask)),
        "selected_delay_bin": best_index,
        "spectral_rate_bpm": peak_frequency * 60.0,
        "peak_interval_rate_bpm": peak_rate,
        "detected_peaks": int(peaks.size),
        "plausible_intervals": int(plausible_ibi.size),
        "peak_to_median_psd_db": pnr_db,
    }


def analyze_capture(path: str | Path, window_s: float = 30.0, start_host_time_s: float | None = None):
    times, csi, active_mask, rssi, rates = load_iq_capture(path, start_host_time_s)
    if window_s < 12:
        raise ValueError("--window-s must be at least 12 seconds")
    windows = []
    start = 0
    while start < times[-1]:
        end = start + window_s
        selection = (times >= start) & (times < end)
        if selection.sum() >= 2 and times[selection][-1] - times[selection][0] >= 12:
            result = analyze_window(times[selection], csi[selection], active_mask)
            result.update({
                "start_s": float(times[selection][0]),
                "end_s": float(times[selection][-1]),
                "mean_rssi_dbm": float(np.mean(rssi[selection])),
                "rate_counts": {
                    str(int(rate)): int(count)
                    for rate, count in zip(*np.unique(rates[selection], return_counts=True))
                },
            })
            windows.append(result)
        start = end
    return {
        "capture": str(path),
        "experimental_only": True,
        "pipeline": [
            "per-packet linear phase-slope/intercept regression",
            "64-bin IFFT delay-domain decomposition",
            "delay-bin cardiac-band Welch PSD selection",
            "Hampel spike conditioning and 0.8-2.5 Hz Butterworth bandpass",
            "peak intervals and spectral peak converted to BPM",
        ],
        "input_packets": int(len(times)),
        "active_subcarriers": int(np.count_nonzero(active_mask)),
        "window_s": window_s,
        "windows": windows,
        "limitations": [
            "Requires new captures containing signed raw I/Q; magnitude-only historical captures cannot support phase analysis.",
            "Synthetic or algorithmic output is not validated heart rate and is not suitable for medical or sleep monitoring.",
            "Use independent ECG/PPG ground truth and controlled still-subject recordings before interpreting estimates.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--window-s", type=float, default=30.0)
    parser.add_argument("--start-host-time-s", type=float)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = analyze_capture(args.capture, args.window_s, args.start_host_time_s)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    output = args.output or args.capture.with_suffix(".heart-rate.json")
    with output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(f"Saved experimental heart-rate report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

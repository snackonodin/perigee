"""CSI parsing, resampling, breathing features, and event/tap alignment."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import butter, find_peaks, periodogram, sosfiltfilt

N_SUBCARRIERS = 64
TIMESTAMP_MODULUS = 2**32
RAW_FIELDS = [
    "ts_us", "mac", "rssi", "rate", "sig_mode", "len",
    *(f"amp_{index:02d}" for index in range(N_SUBCARRIERS)),
]
EVENT_FIELDS = [
    "event_id", "session_id", "host_time_s", "host_time_wall_s",
    "device_time_s", "type", "source", "operator", "label",
]
C_M_S = 299_792_458.0


@dataclass
class Capture:
    path: Path
    metadata: dict[str, Any]
    device_time_s: np.ndarray
    host_time_s: np.ndarray
    amplitudes: np.ndarray
    rssi_dbm: np.ndarray
    macs: np.ndarray
    rates: np.ndarray
    signal_modes: np.ndarray
    packet_rate_hz: float
    largest_gap_s: float
    gaps_over_50ms: int
    active_mask: np.ndarray
    raw_packet_count: int = 0
    nonincreasing_timestamp_count: int = 0
    sub_2ms_device_intervals: int = 0
    sub_2ms_host_intervals: int = 0
    weak_rssi_packet_count: int = 0
    rate_counts: dict[int, int] | None = None


def _read_metadata(path: Path) -> dict[str, Any]:
    meta_path = path.with_suffix(".json")
    if not meta_path.exists():
        return {}
    with meta_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_capture(path: str | Path, phone_mac: str | None = None) -> Capture:
    """Load a capture CSV, filter to the selected phone's legacy CSI packets."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Capture CSV does not exist: {path}")

    metadata = _read_metadata(path)
    if phone_mac is None:
        phone_mac = metadata.get("phone_mac")
    records: list[list[float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(RAW_FIELDS).difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            try:
                ts = int(row["ts_us"])
                mac = row["mac"].strip().lower()
                rssi = int(row["rssi"])
                rate = int(row["rate"])
                sig_mode = int(row["sig_mode"])
                length = int(row["len"])
                amps = [float(row[field]) for field in RAW_FIELDS[6:]]
                host_time = float(row["host_time_s"])
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"Invalid packet on CSV row {line_number}: {exc}") from exc
            if not 0 <= ts < TIMESTAMP_MODULUS:
                raise ValueError(f"Timestamp out of uint32 range on CSV row {line_number}")
            if not np.isfinite(host_time) or not np.isfinite(amps).all():
                raise ValueError(f"Non-finite packet data on CSV row {line_number}")
            if length < 2 or length > 128:
                continue
            if sig_mode != 0:
                continue
            if phone_mac and mac != phone_mac.strip().lower().replace(":", ""):
                continue
            # The sketch prints one magnitude per (imaginary, real) byte pair.
            amp_count = min(length // 2, N_SUBCARRIERS)
            amps[amp_count:] = [0.0] * (N_SUBCARRIERS - amp_count)
            records.append([ts, host_time, rssi, rate, sig_mode, *amps, mac])

    if len(records) < 2:
        raise ValueError("Fewer than two matching legacy CSI packets were found")

    records.sort(key=lambda item: item[1])
    raw_packet_count = len(records)
    raw_rate_counts = {
        int(rate): int(count)
        for rate, count in zip(*np.unique(
            np.asarray([row[3] for row in records], dtype=int),
            return_counts=True,
        ))
    }
    unwrapped_values = []
    kept_records = []
    wrap_offset = 0
    previous_raw = int(records[0][0])
    previous_unwrapped = previous_raw
    nonincreasing_timestamp_count = 0
    sub_2ms_device_intervals = 0
    sub_2ms_host_intervals = 0
    host_times = np.asarray([row[1] for row in records], dtype=float)
    rssi_values = np.asarray([row[2] for row in records], dtype=float)
    weak_rssi_packet_count = 0
    for index, value in enumerate(rssi_values):
        left = np.searchsorted(host_times, host_times[index] - 0.5, side="left")
        right = np.searchsorted(host_times, host_times[index] + 0.5, side="right")
        local_median = float(np.median(rssi_values[left:right]))
        if value < local_median - 4.0:
            weak_rssi_packet_count += 1

    for index, row in enumerate(records):
        current = int(row[0])
        if current < previous_raw and previous_raw - current > TIMESTAMP_MODULUS // 2:
            wrap_offset += TIMESTAMP_MODULUS
        candidate = current + wrap_offset
        if index:
            device_delta_us = candidate - previous_unwrapped
            host_delta_s = row[1] - records[index - 1][1]
            if device_delta_us <= 0:
                nonincreasing_timestamp_count += 1
            elif device_delta_us < 2000:
                sub_2ms_device_intervals += 1
            if 0 < host_delta_s < 0.002:
                sub_2ms_host_intervals += 1
        previous_raw = current
        previous_unwrapped = candidate
        if kept_records and candidate <= unwrapped_values[-1]:
            continue
        kept_records.append(row)
        unwrapped_values.append(float(candidate))
    records = kept_records
    if len(records) < 2:
        raise ValueError("Fewer than two increasing CSI timestamps were found")
    unwrapped = np.asarray(unwrapped_values, dtype=float)
    host = np.asarray([row[1] for row in records], dtype=float)
    device = (unwrapped - unwrapped[0]) / 1_000_000.0
    positive_dt = np.diff(device)
    positive_dt = positive_dt[positive_dt > 0]
    if positive_dt.size == 0:
        raise ValueError("CSI timestamps do not advance")
    largest_gap = float(np.max(positive_dt))
    packet_rate = float(1.0 / np.median(positive_dt))
    amp_matrix = np.asarray([row[5:5 + N_SUBCARRIERS] for row in records], dtype=float)
    active_mask = np.mean(amp_matrix > 0, axis=0) >= 0.99
    if np.count_nonzero(active_mask) < 8:
        raise ValueError("Fewer than eight consistently non-zero subcarriers were found")

    return Capture(
        path=path,
        metadata=metadata,
        device_time_s=device,
        host_time_s=host,
        amplitudes=amp_matrix,
        rssi_dbm=np.asarray([row[2] for row in records], dtype=float),
        rates=np.asarray([row[3] for row in records], dtype=int),
        signal_modes=np.asarray([row[4] for row in records], dtype=int),
        macs=np.asarray([row[-1] for row in records], dtype=str),
        packet_rate_hz=packet_rate,
        largest_gap_s=largest_gap,
        gaps_over_50ms=int(np.count_nonzero(positive_dt > 0.05)),
        active_mask=active_mask,
        raw_packet_count=raw_packet_count,
        nonincreasing_timestamp_count=nonincreasing_timestamp_count,
        sub_2ms_device_intervals=sub_2ms_device_intervals,
        sub_2ms_host_intervals=sub_2ms_host_intervals,
        weak_rssi_packet_count=weak_rssi_packet_count,
        rate_counts=raw_rate_counts,
    )


def packet_quality_report(capture: Capture) -> dict[str, Any]:
    """Summarize packet anomalies without removing those packets from the capture."""
    return {
        "packet_count": capture.raw_packet_count or int(capture.device_time_s.size),
        "analysis_packet_count": int(capture.device_time_s.size),
        "packet_rate_hz": capture.packet_rate_hz,
        "rssi_median_dbm": float(np.median(capture.rssi_dbm)),
        "rssi_p05_dbm": float(np.percentile(capture.rssi_dbm, 5)),
        "rssi_p95_dbm": float(np.percentile(capture.rssi_dbm, 95)),
        "largest_gap_s": capture.largest_gap_s,
        "gaps_over_50ms": capture.gaps_over_50ms,
        "nonincreasing_timestamps_skipped": capture.nonincreasing_timestamp_count,
        "device_intervals_under_2ms": capture.sub_2ms_device_intervals,
        "host_receive_intervals_under_2ms": capture.sub_2ms_host_intervals,
        "weak_rssi_packets_below_local_median_by_4db": capture.weak_rssi_packet_count,
        "rate_counts": {
            str(rate): count for rate, count in (capture.rate_counts or {}).items()
        },
        "active_subcarrier_count": int(capture.active_mask.sum()),
        "inactive_subcarriers": np.flatnonzero(~capture.active_mask).astype(int).tolist(),
    }


def compare_to_empty_reference(
    capture: Capture, empty_reference: Capture
) -> dict[str, Any]:
    """Compare link quality with a geometry-matched empty-room capture."""
    if empty_reference.metadata.get("condition") not in (None, "empty"):
        raise ValueError("Selected empty reference is not labeled condition='empty'")
    if (capture.metadata.get("session_id") and empty_reference.metadata.get("session_id")
            and capture.metadata["session_id"] != empty_reference.metadata["session_id"]):
        raise ValueError("Capture and empty reference must belong to the same session")
    geometry_fields = (
        "arrangement", "beta_deg", "position_label", "position_offset_cm",
        "phone_chest_distance_m", "receiver_chest_distance_m", "distance_m",
        "phone_height_cm", "receiver_height_cm", "phone_orientation",
        "receiver_orientation", "wifi_channel",
    )
    mismatches = [
        key for key in geometry_fields
        if capture.metadata.get(key) is not None
        and empty_reference.metadata.get(key) is not None
        and capture.metadata.get(key) != empty_reference.metadata.get(key)
    ]
    if mismatches:
        raise ValueError(
            "Capture and empty reference geometry differs for: " + ", ".join(mismatches)
        )
    if set(capture.macs) != set(empty_reference.macs):
        raise ValueError("Capture and empty reference phone MACs do not match")
    return {
        "empty_reference_capture": str(empty_reference.path),
        "rssi_loss_vs_empty_db": float(
            np.median(empty_reference.rssi_dbm) - np.median(capture.rssi_dbm)
        ),
        "packet_rate_delta_vs_empty_hz": float(
            capture.packet_rate_hz - empty_reference.packet_rate_hz
        ),
    }


def bistatic_prediction(
    beta_deg: float,
    displacement_mm: float = 5.0,
    carrier_frequency_ghz: float = 2.412,
) -> dict[str, float]:
    """Return ideal reflected-path and phase changes for chest displacement."""
    if not np.isfinite(beta_deg) or not 0.0 <= beta_deg <= 180.0:
        raise ValueError("Bistatic angle beta must be between 0 and 180 degrees")
    if (not np.isfinite(displacement_mm) or not np.isfinite(carrier_frequency_ghz)
            or displacement_mm <= 0 or carrier_frequency_ghz <= 0):
        raise ValueError("Displacement and carrier frequency must be positive")
    beta_rad = math.radians(beta_deg)
    path_change_m = 2.0 * displacement_mm / 1000.0 * math.cos(beta_rad / 2.0)
    wavelength_m = C_M_S / (carrier_frequency_ghz * 1_000_000_000.0)
    return {
        "beta_deg": float(beta_deg),
        "chest_displacement_mm": float(displacement_mm),
        "carrier_frequency_ghz": float(carrier_frequency_ghz),
        "wavelength_m": wavelength_m,
        "path_change_mm": path_change_m * 1000.0,
        "phase_change_rad": 2.0 * math.pi * path_change_m / wavelength_m,
    }


def fit_clock_map(host_time_s: np.ndarray, device_time_s: np.ndarray) -> dict[str, float]:
    """Fit device seconds from host monotonic seconds and quantify residual error."""
    if host_time_s.size < 3 or host_time_s.size != device_time_s.size:
        raise ValueError("At least three paired packet clocks are required")
    slope, offset = np.polyfit(host_time_s, device_time_s, 1)
    residuals = device_time_s - (slope * host_time_s + offset)
    return {
        "slope": float(slope),
        "offset_s": float(offset),
        "rms_residual_ms": float(np.sqrt(np.mean(residuals**2)) * 1000),
        "max_abs_residual_ms": float(np.max(np.abs(residuals)) * 1000),
    }


def update_event_device_times(events_path: str | Path, clock: dict[str, float]) -> None:
    path = Path(events_path)
    if not path.is_file():
        raise FileNotFoundError(f"Event CSV does not exist: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(EVENT_FIELDS).difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    for row in rows:
        host = float(row["host_time_s"])
        row["device_time_s"] = f"{clock['slope'] * host + clock['offset_s']:.9f}"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def read_events(
    path: str | Path, expected_session_id: str | None = None
) -> list[dict[str, Any]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(EVENT_FIELDS).difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        events = []
        for row in reader:
            if row["type"] not in {"breath_tap", "marker"}:
                raise ValueError(f"Unsupported event type {row['type']!r}")
            if expected_session_id and row["session_id"] != expected_session_id:
                raise ValueError(
                    f"Event session_id {row['session_id']!r} does not match "
                    f"expected session_id {expected_session_id!r}"
                )
            if row["type"] == "breath_tap" and row["source"] != "helper_tap_v1":
                raise ValueError(
                    f"Unsupported v1 breath-tap source {row['source']!r}"
                )
            if row["type"] == "breath_tap" and row["device_time_s"]:
                events.append({**row, "device_time_s": float(row["device_time_s"])})
        return sorted(events, key=lambda event: event["device_time_s"])


def resample_packets(
    capture: Capture, sample_rate_hz: float = 20.0, normalize: bool = True
) -> tuple[np.ndarray, np.ndarray, float]:
    """Bin-average packets to a uniform grid and interpolate empty bins."""
    grid_count = int(math.floor(capture.device_time_s[-1] * sample_rate_hz)) + 1
    if grid_count < 2:
        raise ValueError("Capture is too short to resample")
    bin_index = np.floor(capture.device_time_s * sample_rate_hz).astype(int)
    valid_amps = capture.amplitudes[:, capture.active_mask]
    if normalize:
        row_mean = np.mean(valid_amps, axis=1)
        row_mean[row_mean <= 0] = np.nan
        normalized = capture.amplitudes / row_mean[:, None]
        normalized = np.nan_to_num(normalized, nan=0.0, posinf=0.0, neginf=0.0)
    else:
        normalized = capture.amplitudes.copy()

    totals = np.zeros((grid_count, N_SUBCARRIERS), dtype=float)
    counts = np.zeros(grid_count, dtype=int)
    for index, vector in zip(bin_index, normalized):
        if 0 <= index < grid_count:
            totals[index] += vector
            counts[index] += 1
    observed = counts > 0
    if np.count_nonzero(observed) < 2:
        raise ValueError("Too few populated 20 Hz bins")
    matrix = np.zeros_like(totals)
    matrix[observed] = totals[observed] / counts[observed, None]
    positions = np.flatnonzero(observed)
    for column in range(N_SUBCARRIERS):
        matrix[:, column] = np.interp(np.arange(grid_count), positions, matrix[positions, column])
    return np.arange(grid_count) / sample_rate_hz, matrix, float(np.mean(observed))


def hampel_filter(matrix: np.ndarray, sample_rate_hz: float, window_s: float = 1.0) -> np.ndarray:
    """Replace isolated per-carrier spikes using a local median/MAD."""
    width = max(3, int(round(window_s * sample_rate_hz)) | 1)
    size = (width, 1)
    median = median_filter(matrix, size=size, mode="nearest")
    mad = median_filter(np.abs(matrix - median), size=size, mode="nearest")
    threshold = 3.0 * 1.4826 * mad
    outliers = (threshold > 0) & (np.abs(matrix - median) > threshold)
    return np.where(outliers, median, matrix)


def _safe_filter(
    values: np.ndarray, low_hz: float, high_hz: float, sample_rate_hz: float, order: int = 3
) -> np.ndarray:
    if values.shape[0] < 3 * sample_rate_hz:
        raise ValueError("Window is too short for stable zero-phase filtering")
    sos = butter(
        order, [low_hz, high_hz], btype="bandpass", fs=sample_rate_hz, output="sos"
    )
    return sosfiltfilt(sos, values, axis=0)


def _parabolic_peak(frequencies: np.ndarray, power: np.ndarray, index: int) -> float:
    if index <= 0 or index >= len(power) - 1:
        return float(frequencies[index])
    y = np.log(np.maximum(power[index - 1:index + 2], np.finfo(float).tiny))
    denominator = y[0] - 2 * y[1] + y[2]
    offset = 0.0 if denominator == 0 else 0.5 * (y[0] - y[2]) / denominator
    offset = float(np.clip(offset, -1.0, 1.0))
    return float(frequencies[index] + offset * (frequencies[1] - frequencies[0]))


def spectral_rate(signal: np.ndarray, sample_rate_hz: float) -> tuple[float | None, float | None]:
    frequencies, power = periodogram(
        signal, fs=sample_rate_hz, window="hann", detrend="linear", scaling="spectrum"
    )
    rate_band = (frequencies >= 0.15) & (frequencies <= 0.5)
    noise_band = (frequencies >= 0.1) & (frequencies <= 0.7)
    if np.count_nonzero(rate_band) < 2:
        return None, None
    candidate_indices = np.flatnonzero(rate_band)
    peak_index = int(candidate_indices[np.argmax(power[rate_band])])
    noise_mask = noise_band & (np.abs(frequencies - frequencies[peak_index]) > 0.05)
    noise = float(np.median(power[noise_mask])) if np.any(noise_mask) else 0.0
    pnr_db = 10.0 * np.log10(max(power[peak_index], 1e-20) / max(noise, 1e-20))
    frequency = float(np.clip(_parabolic_peak(frequencies, power, peak_index), 0.15, 0.5))
    return frequency * 60.0, float(pnr_db)


def _time_domain_peaks(
    signal: np.ndarray, sample_rate_hz: float
) -> tuple[np.ndarray, float | None]:
    filtered = _safe_filter(signal, 0.1, 0.5, sample_rate_hz, order=3)
    min_distance = int(sample_rate_hz * 60.0 / 30.0)
    prominence = max(float(np.std(filtered) * 0.15), 1e-8)
    peaks, _ = find_peaks(filtered, distance=min_distance, prominence=prominence)
    if peaks.size < 2:
        return peaks, None
    intervals = np.diff(peaks) / sample_rate_hz
    return peaks, float(60.0 / np.median(intervals))


def time_domain_rate(signal: np.ndarray, sample_rate_hz: float) -> float | None:
    """Estimate breathing rate from the median interval between filtered peaks."""
    _, rate = _time_domain_peaks(signal, sample_rate_hz)
    return rate


def _rank_subcarriers(matrix: np.ndarray, sample_rate_hz: float, mask: np.ndarray) -> np.ndarray:
    filtered = _safe_filter(matrix, 0.05, 2.0, sample_rate_hz)
    frequencies, powers = periodogram(filtered, fs=sample_rate_hz, axis=0, window="hann")
    breath = (frequencies >= 0.15) & (frequencies <= 0.5)
    noise = (frequencies >= 0.5) & (frequencies <= 2.0)
    numerator = np.sum(powers[breath], axis=0)
    denominator = np.sum(powers[noise], axis=0) + 1e-20
    snr = numerator / denominator
    candidates = np.flatnonzero(mask)
    return candidates[np.argsort(snr[candidates])[::-1][:min(10, candidates.size)]]


def pca_breath_estimates(
    matrix: np.ndarray, sample_rate_hz: float
) -> tuple[float | None, float | None, float | None]:
    centered = matrix - np.mean(matrix, axis=0)
    scores, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
    components = scores * singular_values[None, :]
    frequencies, powers = periodogram(
        components, fs=sample_rate_hz, axis=0, window="hann",
        detrend="linear", scaling="spectrum",
    )
    rate_band = (frequencies >= 0.15) & (frequencies <= 0.5)
    noise_band = (frequencies >= 0.1) & (frequencies <= 0.7)
    if np.count_nonzero(rate_band) < 2:
        return None, None, None
    rate_indices = np.flatnonzero(rate_band)
    peak_indices = rate_indices[np.argmax(powers[rate_band], axis=0)]
    pnrs = []
    for column, peak_index in enumerate(peak_indices):
        noise_mask = noise_band & (np.abs(frequencies - frequencies[peak_index]) > 0.05)
        noise = float(np.median(powers[noise_mask, column])) if np.any(noise_mask) else 0.0
        pnrs.append(
            10.0 * np.log10(max(powers[peak_index, column], 1e-20) / max(noise, 1e-20))
        )
    best_index = int(np.argmax(pnrs))
    best_frequency = _parabolic_peak(frequencies, powers[:, best_index], int(peak_indices[best_index]))
    return best_frequency * 60.0, float(pnrs[best_index]), float(best_index + 1)


def motion_feature(
    matrix: np.ndarray, sample_rate_hz: float, breath_rate_bpm: float | None
) -> float:
    """Maximum residual 0.8-3 Hz power in non-overlapping two-second segments."""
    values = matrix.copy()
    if breath_rate_bpm is not None:
        frequency = breath_rate_bpm / 60.0
        t = np.arange(values.shape[0]) / sample_rate_hz
        for harmonic in range(1, 6):
            f = frequency * harmonic
            if not 0.8 <= f <= 3.0:
                continue
            design = np.column_stack((np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)))
            coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
            values -= design @ coefficients
    filtered = _safe_filter(values, 0.8, min(3.0, sample_rate_hz * 0.45), sample_rate_hz, order=2)
    frame = max(4, int(round(2.0 * sample_rate_hz)))
    if filtered.shape[0] < frame:
        return float(np.mean(filtered**2))
    powers = [
        float(np.mean(filtered[start:start + frame] ** 2))
        for start in range(0, filtered.shape[0] - frame + 1, frame)
    ]
    return max(powers, default=0.0)


def score_windows(
    capture: Capture,
    settings: dict[str, Any],
    *,
    normalize: bool = True,
    hop_s: float | None = None,
    max_duration_s: float | None = None,
) -> list[dict[str, Any]]:
    sample_rate = float(settings["resample_rate_hz"])
    window_s = float(settings["window_s"])
    hop_s = float(settings["hop_s"] if hop_s is None else hop_s)
    grid_t, matrix, _ = resample_packets(capture, sample_rate, normalize=normalize)
    rows = []
    window_samples = int(round(window_s * sample_rate))
    hop_samples = max(1, int(round(hop_s * sample_rate)))
    limit_samples = (
        matrix.shape[0]
        if max_duration_s is None
        else min(matrix.shape[0], int(round(max_duration_s * sample_rate)))
    )
    packet_bins = np.floor(capture.device_time_s * sample_rate).astype(int)
    for start in range(0, limit_samples - window_samples + 1, hop_samples):
        stop = start + window_samples
        raw_window = matrix[start:stop]
        coverage = float(np.unique(packet_bins[(packet_bins >= start) & (packet_bins < stop)]).size)
        coverage /= window_samples
        active = capture.active_mask
        filtered = hampel_filter(raw_window[:, active], sample_rate)
        filtered = _safe_filter(filtered, 0.05, min(3.0, sample_rate * 0.45), sample_rate)
        selected_local = _rank_subcarriers(filtered, sample_rate, np.ones(filtered.shape[1], dtype=bool))
        selected = filtered[:, selected_local]
        selected_std = np.std(selected, axis=0)
        safe_std = np.where(selected_std > 1e-12, selected_std, 1.0)
        normalized = (selected - np.mean(selected, axis=0)) / safe_std
        frequencies, spectra = periodogram(
            normalized, fs=sample_rate, axis=0, window="hann", scaling="spectrum"
        )
        aggregate_power = np.mean(spectra, axis=1)
        band = (frequencies >= 0.15) & (frequencies <= 0.5)
        candidates = np.flatnonzero(band)
        peak_index = int(candidates[np.argmax(aggregate_power[band])])
        noise_mask = (
            (frequencies >= 0.1) & (frequencies <= 0.7)
            & (np.abs(frequencies - frequencies[peak_index]) > 0.05)
        )
        noise = float(np.median(aggregate_power[noise_mask])) if np.any(noise_mask) else 0.0
        pnr_db = float(
            10.0 * np.log10(max(aggregate_power[peak_index], 1e-20) / max(noise, 1e-20))
        )
        frequency = float(np.clip(
            _parabolic_peak(frequencies, aggregate_power, peak_index), 0.15, 0.5
        ))
        rate_a = frequency * 60.0
        peak_samples, rate_b = _time_domain_peaks(normalized[:, 0], sample_rate)
        peak_times = grid_t[start] + peak_samples / sample_rate
        median_peak_interval = (
            float(np.median(np.diff(peak_times))) if peak_times.size >= 2 else None
        )
        predicted_next_peak = (
            float(peak_times[-1] + median_peak_interval)
            if median_peak_interval is not None else None
        )
        pca_rate, pca_pnr, pca_component = pca_breath_estimates(filtered, sample_rate)

        # Compare with unnormalized amplitudes through a second, independent pass.
        motion = motion_feature(raw_window[:, active], sample_rate, rate_a)
        delta = (
            abs(rate_a - rows[-1]["rate_A"])
            if rows and rows[-1]["rate_A"] is not None else None
        )
        rows.append({
            "window_id": len(rows),
            "t_start": float(grid_t[start]),
            "t_end": float(grid_t[start] + window_s),
            "rate_A": float(rate_a),
            "rate_B": rate_b,
            "breath_peak_times_s": peak_times.tolist(),
            "median_peak_interval_s": median_peak_interval,
            "predicted_next_peak_s": predicted_next_peak,
            "pnr_db": pnr_db,
            "pca_rate_A": pca_rate,
            "pca_pnr_db": pca_pnr,
            "pca_component": pca_component,
            "ab_diff_bpm": None if rate_b is None else float(abs(rate_a - rate_b)),
            "motion_feature": motion,
            "delta_prev_bpm": None if delta is None else float(delta),
            "coverage": coverage,
        })
    return rows


def signal_scan_windows(
    capture: Capture, settings: dict[str, Any]
) -> list[dict[str, Any]]:
    """Run the established exploratory scan with non-overlapping windows."""
    return score_windows(capture, settings, hop_s=float(settings["window_s"]))


def session_pnr_floor(
    capture: Capture,
    settings: dict[str, Any],
    *,
    duration_s: float = 120.0,
    quantile: float = 0.95,
    margin_db: float = 1.0,
) -> dict[str, Any]:
    """Derive a session-local presence floor from the first two minutes of empty data."""
    capture_duration = capture.device_time_s[-1] - capture.device_time_s[0]
    if capture_duration + 1.0 / float(settings["resample_rate_hz"]) < duration_s:
        raise ValueError(f"Adaptive empty reference must be at least {duration_s:g} seconds")
    windows = score_windows(
        capture,
        settings,
        hop_s=float(settings["window_s"]),
        max_duration_s=duration_s,
    )
    values = [
        window["pnr_db"] for window in windows
        if window["coverage"] >= float(settings["coverage_min"])
    ]
    if not values:
        raise ValueError("Adaptive empty reference contains no coverage-qualified windows")
    floor = float(np.quantile(values, quantile)) + margin_db
    return {
        "threshold_db": floor,
        "quantile_db_without_margin": float(np.quantile(values, quantile)),
        "margin_db": margin_db,
        "window_count": len(values),
        "duration_s": duration_s,
        "quantile": quantile,
    }


def tap_truth(
    events: list[dict[str, Any]],
    start_s: float,
    end_s: float,
    *,
    minimum_breaths: int = 5,
    max_cv: float = 0.15,
    minimum_interval_ratio: float = 0.5,
    maximum_interval_ratio: float = 1.7,
) -> dict[str, Any]:
    taps = np.asarray(
        [event["device_time_s"] for event in events if start_s <= event["device_time_s"] <= end_s],
        dtype=float,
    )
    all_taps = np.asarray([event["device_time_s"] for event in events], dtype=float)
    intervals = np.diff(all_taps)
    interval_median = float(np.median(intervals)) if intervals.size else None
    flagged_intervals = []
    if interval_median and interval_median > 0:
        flagged = (
            (intervals < minimum_interval_ratio * interval_median)
            | (intervals > maximum_interval_ratio * interval_median)
        )
        flagged_intervals = [
            (float(all_taps[index]), float(all_taps[index + 1]))
            for index in np.flatnonzero(flagged)
        ]
    touches_flag = any(left < end_s and right > start_s for left, right in flagged_intervals)
    local_intervals = np.diff(taps)
    cv = (
        float(np.std(local_intervals, ddof=1) / np.mean(local_intervals))
        if local_intervals.size >= 2 and np.mean(local_intervals) > 0 else None
    )
    rate = (
        float(60.0 * (taps.size - 1) / (taps[-1] - taps[0]))
        if taps.size >= 2 and taps[-1] > taps[0] else None
    )
    reliable = (
        taps.size >= minimum_breaths
        and cv is not None and cv < max_cv
        and not touches_flag
    )
    return {
        "ground_truth_bpm": rate if reliable else None,
        "breath_count": int(taps.size),
        "interval_cv": cv,
        "truth_reliable": bool(reliable),
        "touches_tap_qa_flag": bool(touches_flag),
        "label_source": "helper_tap_v1",
    }


def load_settings(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        settings = json.load(handle)
    required = {
        "resample_rate_hz", "window_s", "hop_s", "coverage_min",
        "packet_rate_min_hz", "pnr_presence_floor_db", "pnr_valid_threshold_db",
        "motion_threshold_normalized", "ab_agreement_max_bpm", "rate_jump_max_bpm",
    }
    missing = required.difference(settings)
    if missing:
        raise ValueError(f"Config is missing fields: {', '.join(sorted(missing))}")
    return settings

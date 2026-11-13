#!/usr/bin/env python3
"""Experimental CSI Doppler and relative-movement analysis from signed I/Q."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import deque
from pathlib import Path

import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.ndimage import median_filter
from scipy.signal import welch

from heart_rate import I_FIELDS, N_SUBCARRIERS, Q_FIELDS, load_iq_capture, sanitize_phase

SPEED_OF_LIGHT_M_S = 299_792_458.0
DEFAULT_CARRIER_HZ = 2.412e9


def _uniform_complex_series(
    times: np.ndarray, values: np.ndarray, sample_rate_hz: float
) -> tuple[np.ndarray, np.ndarray]:
    uniform_times = np.arange(times[0], times[-1], 1.0 / sample_rate_hz)
    if uniform_times.size < 8:
        raise ValueError("Too few samples for Doppler estimation.")
    uniform = np.column_stack([
        np.interp(uniform_times, times, values[:, index].real)
        + 1j * np.interp(uniform_times, times, values[:, index].imag)
        for index in range(values.shape[1])
    ])
    return uniform_times, uniform


def _estimate_doppler(
    times: np.ndarray,
    csi: np.ndarray,
    active_mask: np.ndarray,
    carrier_hz: float = DEFAULT_CARRIER_HZ,
    doppler_factor: float = 1.0,
    snr_gate_db: float = 2.0,
) -> dict[str, float | int | None | bool]:
    """Estimate signed radial-equivalent speed from a moving delay-bin peak."""
    duration = float(times[-1] - times[0])
    if duration < 3.0:
        raise ValueError("Doppler windows must contain at least 3 seconds of data.")
    if not np.isfinite(carrier_hz) or carrier_hz <= 0:
        raise ValueError("Carrier frequency must be positive and finite.")
    if not np.isfinite(doppler_factor) or doppler_factor <= 0:
        raise ValueError("Doppler factor must be positive and finite.")
    median_dt = float(np.median(np.diff(times)))
    sample_rate_hz = min(100.0, 1.0 / median_dt)
    if sample_rate_hz <= 2.0:
        raise ValueError(f"Insufficient packet rate for Doppler analysis: {sample_rate_hz:.2f} Hz")

    clean = sanitize_phase(csi, active_mask)
    delay_bins = np.fft.fftshift(np.fft.ifft(clean, n=N_SUBCARRIERS, axis=1), axes=1)
    uniform_times, uniform_bins = _uniform_complex_series(times, delay_bins, sample_rate_hz)
    nperseg = min(uniform_times.size, max(8, int(round(duration * sample_rate_hz))))
    best_frequency, best_power, best_snr, best_bin = None, -np.inf, -np.inf, None
    best_candidate_snr = -np.inf
    max_doppler_hz = min(8.0, sample_rate_hz / 2.0)

    for bin_index in range(N_SUBCARRIERS):
        signal = uniform_bins[:, bin_index]
        signal = signal - np.mean(signal)
        if np.max(np.abs(signal)) <= np.finfo(float).eps:
            continue
        current_frequency, power = welch(
            signal,
            fs=sample_rate_hz,
            nperseg=nperseg,
            noverlap=nperseg // 2,
            detrend="linear",
            return_onesided=False,
            scaling="spectrum",
        )
        current_frequency = np.fft.fftshift(current_frequency)
        power = np.fft.fftshift(power)
        band = (np.abs(current_frequency) >= 1.0 / duration) & (
            np.abs(current_frequency) <= max_doppler_hz
        )
        if not np.any(band):
            continue
        indices = np.flatnonzero(band)
        peak_index = int(indices[np.argmax(power[band])])
        noise_mask = band & (
            np.abs(current_frequency - current_frequency[peak_index]) > 0.5 / duration
        )
        noise = float(np.median(power[noise_mask])) if np.any(noise_mask) else 0.0
        peak_power = float(power[peak_index])
        snr_db = float(10.0 * np.log10(
            max(peak_power, np.finfo(float).tiny)
            / max(noise, np.finfo(float).tiny)
        ))
        best_candidate_snr = max(best_candidate_snr, snr_db)
        if snr_db > snr_gate_db and peak_power > best_power:
            best_frequency = float(current_frequency[peak_index])
            best_power = peak_power
            best_snr = snr_db
            best_bin = bin_index

    if best_frequency is None or best_bin is None:
        return {
            "doppler_hz": None,
            "radial_velocity_m_s": None,
            "selected_delay_bin": None,
            "doppler_snr_db": (
                float(best_candidate_snr) if np.isfinite(best_candidate_snr) else None
            ),
            "sample_rate_hz": float(sample_rate_hz),
            "doppler_resolution_hz": float(sample_rate_hz / nperseg),
            "wavelength_m": float(SPEED_OF_LIGHT_M_S / carrier_hz),
            "snr_gate_passed": False,
        }
    wavelength_m = SPEED_OF_LIGHT_M_S / carrier_hz
    radial_velocity_m_s = wavelength_m * best_frequency / doppler_factor
    return {
        "doppler_hz": float(best_frequency),
        "radial_velocity_m_s": float(radial_velocity_m_s),
        "selected_delay_bin": int(best_bin),
        "doppler_snr_db": float(best_snr),
        "sample_rate_hz": float(sample_rate_hz),
        "doppler_resolution_hz": float(sample_rate_hz / nperseg),
        "wavelength_m": float(wavelength_m),
        "snr_gate_passed": True,
    }


def _movement_windows(
    times: np.ndarray,
    csi: np.ndarray,
    active_mask: np.ndarray,
    window_s: float,
    hop_s: float,
    carrier_hz: float,
    doppler_factor: float,
) -> list[dict[str, float | int | None | bool]]:
    windows: list[dict[str, float | int | None | bool]] = []
    start_s = 0.0
    while start_s + window_s <= times[-1] + 1e-9:
        selection = (times >= start_s) & (times < start_s + window_s)
        if np.count_nonzero(selection) >= 8:
            estimate = _estimate_doppler(
                times[selection],
                csi[selection],
                active_mask,
                carrier_hz,
                doppler_factor,
            )
            estimate.update({
                "start_s": float(times[selection][0]),
                "end_s": float(times[selection][-1]),
                "center_s": float((times[selection][0] + times[selection][-1]) / 2.0),
            })
            windows.append(estimate)
        start_s += hop_s
    if len(windows) < 2:
        raise ValueError(
            "Capture is too short for at least two movement estimates; "
            "record longer or use a shorter window."
        )
    return windows


def analyze_capture(
    path: str | Path,
    *,
    window_s: float = 4.0,
    hop_s: float = 1.0,
    carrier_hz: float = DEFAULT_CARRIER_HZ,
    doppler_factor: float = 1.0,
    start_host_time_s: float | None = None,
) -> dict:
    if not np.isfinite(window_s) or window_s < 3.0:
        raise ValueError("--window-s must be at least 3 seconds.")
    if not np.isfinite(hop_s) or hop_s <= 0 or hop_s > window_s:
        raise ValueError("--hop-s must be positive and no longer than --window-s.")
    times, csi, active_mask, rssi, _rates = load_iq_capture(
        path, start_host_time_s
    )
    windows = _movement_windows(
        times, csi, active_mask, window_s, hop_s, carrier_hz, doppler_factor
    )
    velocity = np.asarray(
        [
            np.nan if window["radial_velocity_m_s"] is None
            else float(window["radial_velocity_m_s"])
            for window in windows
        ],
        dtype=float,
    )
    center_times = np.asarray([window["center_s"] for window in windows], dtype=float)
    valid_velocity = np.isfinite(velocity)
    if np.count_nonzero(valid_velocity) < 2:
        raise ValueError(
            "Fewer than two windows passed the 2 dB Doppler SNR gate; "
            "check I/Q quality or use a clearer movement trial."
        )
    velocity = np.interp(center_times, center_times[valid_velocity], velocity[valid_velocity])
    # Remove the robust stationary offset before integrating; the result remains relative.
    corrected_velocity = velocity - float(np.median(velocity))
    smoothed_velocity = median_filter(corrected_velocity, size=3, mode="nearest")
    displacement_m = cumulative_trapezoid(
        smoothed_velocity, center_times, initial=0.0
    )
    acceleration = np.gradient(smoothed_velocity, center_times)
    abs_acceleration = np.abs(acceleration)
    accel_median = float(np.median(abs_acceleration))
    accel_mad = float(np.median(np.abs(abs_acceleration - accel_median)))
    movement_threshold = accel_median + 6.0 * 1.4826 * accel_mad
    intensity_scale = float(np.percentile(abs_acceleration, 99))
    if intensity_scale <= np.finfo(float).eps:
        intensity_scale = 1.0

    for index, window in enumerate(windows):
        intensity = min(100.0, 100.0 * abs_acceleration[index] / intensity_scale)
        window.update({
            "relative_displacement_m": float(displacement_m[index]),
            "relative_displacement_cm": float(displacement_m[index] * 100.0),
            "smoothed_radial_velocity_m_s": float(smoothed_velocity[index]),
            "acceleration_m_s2": float(acceleration[index]),
            "movement_intensity_0_100": (
                float(intensity) if valid_velocity[index] else None
            ),
            "sudden_movement": bool(
                valid_velocity[index] and abs_acceleration[index] > movement_threshold
            ),
        })

    return {
        "capture": str(path),
        "experimental_only": True,
        "input_packets": int(times.size),
        "duration_s": float(times[-1]),
        "packet_rate_hz": float(1.0 / np.median(np.diff(times))),
        "active_subcarriers": int(np.count_nonzero(active_mask)),
        "median_rssi_dbm": float(np.median(rssi)),
        "carrier_hz": float(carrier_hz),
        "doppler_factor": float(doppler_factor),
        "window_s": float(window_s),
        "hop_s": float(hop_s),
        "doppler_snr_gate_db": 2.0,
        "movement_acceleration_threshold_m_s2": float(movement_threshold),
        "delay_resolution_m_at_20mhz": float(SPEED_OF_LIGHT_M_S / 20e6),
        "windows": windows,
        "limitations": [
            "Requires new signed I/Q captures; magnitude-only recordings cannot recover phase or Doppler.",
            "Velocity is a radial-equivalent estimate using v = wavelength * Doppler frequency / doppler_factor; unknown bistatic geometry may change the scale.",
            "The integrated displacement is relative, drift-corrected movement, not absolute body position.",
            "At 20 MHz bandwidth, delay resolution is about 15 m; IFFT bins do not isolate individual body reflections in a typical room.",
            "The 0-100 movement intensity is normalized within this recording, not a calibrated physical severity scale.",
            "Sudden-movement flags use a robust within-recording acceleration threshold and are not a trained classifier.",
            "ROCKET/MORIC classification is not included until labeled movement captures are collected for training and held-out validation.",
            "Not validated for sleep, clinical, or medical monitoring.",
        ],
    }


def _follow_live_capture(
    path: Path,
    *,
    window_s: float,
    hop_s: float,
    carrier_hz: float,
    doppler_factor: float,
    phone_mac: str | None,
) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Live capture CSV does not exist: {path}")
    expected_mac = (
        phone_mac.strip().lower().replace(":", "") if phone_mac else None
    )
    if expected_mac and (
        len(expected_mac) != 12
        or any(character not in "0123456789abcdef" for character in expected_mac)
    ):
        raise ValueError("--phone-mac must be a 6-byte hexadecimal MAC address.")

    packet_fields = {"ts_us", "mac", "sig_mode", "len", *I_FIELDS, *Q_FIELDS}
    print(
        f"Following {path}; last {window_s:g}s, update every {hop_s:g}s. "
        "Press Ctrl-C to stop.",
        flush=True,
    )
    if expected_mac is None:
        print("No phone MAC filter set; all I/Q CSI rows will be considered.", flush=True)

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"Capture CSV is empty: {path}")
        missing = packet_fields.difference(header)
        if missing:
            if missing.intersection((*I_FIELDS, *Q_FIELDS)):
                raise ValueError(
                    f"{path} has no signed I/Q columns; use I/Q-output firmware "
                    "and the logger that stores csi_i_XX/csi_q_XX."
                )
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")

        packet_buffer: deque[tuple[float, np.ndarray]] = deque()
        velocity_history: deque[float] = deque(maxlen=61)
        acceleration_history: deque[float] = deque(maxlen=61)
        previous_raw_timestamp: int | None = None
        previous_timestamp_us: int | None = None
        wrap_offset = 0
        first_timestamp_us: int | None = None
        next_update_s = window_s
        previous_center_s: float | None = None
        previous_corrected_velocity: float | None = None
        relative_displacement_m = 0.0
        while True:
            line = handle.readline()
            if not line:
                time.sleep(0.1)
                continue
            values = next(csv.reader([line]))
            if len(values) != len(header):
                raise ValueError("Malformed row appended to live capture CSV.")
            row = dict(zip(header, values))
            if expected_mac and row["mac"].strip().lower().replace(":", "") != expected_mac:
                continue
            if int(row["sig_mode"]) != 0:
                continue
            if any(row[field] == "" for field in (*I_FIELDS, *Q_FIELDS)):
                raise ValueError(
                    "Live capture contains blank I/Q values; use signed-I/Q "
                    "firmware on the receiver before running movement analysis."
                )
            try:
                raw_timestamp = int(row["ts_us"])
                length = int(row["len"])
                count = min(length // 2, N_SUBCARRIERS)
                i_values = np.asarray([float(row[field]) for field in I_FIELDS[:count]])
                q_values = np.asarray([float(row[field]) for field in Q_FIELDS[:count]])
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"Invalid I/Q packet in live capture: {exc}") from exc
            if not 0 <= raw_timestamp < 2**32 or length < 2 or length > 128:
                continue
            if not np.isfinite(i_values).all() or not np.isfinite(q_values).all():
                raise ValueError("Non-finite I/Q packet in live capture.")

            if (
                previous_raw_timestamp is not None
                and raw_timestamp < previous_raw_timestamp
                and previous_raw_timestamp - raw_timestamp > 2**31
            ):
                wrap_offset += 2**32
            unwrapped_timestamp = raw_timestamp + wrap_offset
            previous_raw_timestamp = raw_timestamp
            if (
                previous_timestamp_us is not None
                and unwrapped_timestamp - previous_timestamp_us < 2000
            ):
                continue
            previous_timestamp_us = unwrapped_timestamp
            if first_timestamp_us is None:
                first_timestamp_us = unwrapped_timestamp
            relative_s = (unwrapped_timestamp - first_timestamp_us) / 1e6
            vector = np.zeros(N_SUBCARRIERS, dtype=np.complex128)
            vector[:count] = i_values + 1j * q_values
            packet_buffer.append((relative_s, vector))
            while packet_buffer and packet_buffer[0][0] < relative_s - window_s - 0.1:
                packet_buffer.popleft()
            if relative_s + 1e-9 < next_update_s:
                continue

            selected = [
                (packet_time, vector)
                for packet_time, vector in packet_buffer
                if packet_time >= relative_s - window_s
            ]
            if len(selected) < 8:
                next_update_s = relative_s + hop_s
                continue
            window_times = np.asarray([item[0] for item in selected])
            window_csi = np.asarray([item[1] for item in selected])
            active_mask = np.mean(np.abs(window_csi) > 0, axis=0) >= 0.99
            if np.count_nonzero(active_mask) < 8:
                print(f"{relative_s:7.1f}s | insufficient active I/Q subcarriers", flush=True)
                next_update_s = relative_s + hop_s
                continue
            estimate = _estimate_doppler(
                window_times, window_csi, active_mask, carrier_hz, doppler_factor
            )
            center_s = float((window_times[0] + window_times[-1]) / 2.0)
            if not estimate["snr_gate_passed"]:
                print(
                    f"{relative_s:7.1f}s | movement estimate unavailable "
                    f"(best Doppler SNR {estimate['doppler_snr_db']})",
                    flush=True,
                )
                next_update_s = relative_s + hop_s
                continue

            velocity = float(estimate["radial_velocity_m_s"])
            baseline = float(np.median(velocity_history)) if velocity_history else 0.0
            corrected_velocity = velocity - baseline
            velocity_history.append(velocity)
            if (
                previous_center_s is not None
                and previous_corrected_velocity is not None
                and center_s > previous_center_s
            ):
                relative_displacement_m += (
                    (previous_corrected_velocity + corrected_velocity)
                    * 0.5 * (center_s - previous_center_s)
                )
                acceleration = (
                    corrected_velocity - previous_corrected_velocity
                ) / (center_s - previous_center_s)
                acceleration_history.append(abs(acceleration))
                median_acceleration = float(np.median(acceleration_history))
                mad = float(np.median(np.abs(
                    np.asarray(acceleration_history) - median_acceleration
                )))
                threshold = median_acceleration + 6.0 * 1.4826 * mad
                scale = float(np.percentile(acceleration_history, 99))
                intensity = min(100.0, 100.0 * abs(acceleration) / max(scale, 1e-9))
                sudden = abs(acceleration) > threshold
                acceleration_text = f"{acceleration:+.3f}m/s2"
                intensity_text = f"{intensity:.0f}/100"
            else:
                acceleration = 0.0
                sudden = False
                acceleration_text = "warming up"
                intensity_text = "n/a"
            print(
                f"{relative_s:7.1f}s | v={velocity:+.4f}m/s | "
                f"relative={relative_displacement_m * 100:+.2f}cm | "
                f"a={acceleration_text} | intensity={intensity_text} | "
                f"movement={'YES' if sudden else 'no'} | "
                f"SNR={float(estimate['doppler_snr_db']):.1f}dB",
                flush=True,
            )
            previous_center_s = center_s
            previous_corrected_velocity = corrected_velocity
            next_update_s = relative_s + hop_s


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--window-s", type=float, default=4.0)
    parser.add_argument("--hop-s", type=float, default=1.0)
    parser.add_argument("--carrier-ghz", type=float, default=2.412)
    parser.add_argument(
        "--doppler-factor", type=float, default=1.0,
        help="converts Doppler frequency to speed: v=lambda*f_d/factor (default 1)",
    )
    parser.add_argument("--start-host-time-s", type=float)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--follow", action="store_true",
        help="follow a live logger CSV instead of analyzing a completed capture",
    )
    parser.add_argument("--phone-mac", help="optional phone MAC filter for live following")
    args = parser.parse_args()
    if args.follow:
        if not np.isfinite(args.window_s) or args.window_s < 3.0:
            parser.error("--window-s must be at least 3 seconds")
        if not np.isfinite(args.hop_s) or args.hop_s <= 0 or args.hop_s > args.window_s:
            parser.error("--hop-s must be positive and no longer than --window-s")
        try:
            _follow_live_capture(
                args.capture,
                window_s=args.window_s,
                hop_s=args.hop_s,
                carrier_hz=args.carrier_ghz * 1e9,
                doppler_factor=args.doppler_factor,
                phone_mac=args.phone_mac,
            )
        except KeyboardInterrupt:
            print("\nLive movement viewer stopped.", flush=True)
            return 0
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        return 0
    try:
        report = analyze_capture(
            args.capture,
            window_s=args.window_s,
            hop_s=args.hop_s,
            carrier_hz=args.carrier_ghz * 1e9,
            doppler_factor=args.doppler_factor,
            start_host_time_s=args.start_host_time_s,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    output = args.output or args.capture.with_suffix(".movement.json")
    csv_output = output.with_suffix(".csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "start_s", "end_s", "center_s", "doppler_hz", "radial_velocity_m_s",
        "smoothed_radial_velocity_m_s", "relative_displacement_m",
        "relative_displacement_cm", "acceleration_m_s2",
        "movement_intensity_0_100", "sudden_movement", "selected_delay_bin",
        "doppler_snr_db", "snr_gate_passed",
    ]
    with csv_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: window[key] for key in fieldnames} for window in report["windows"])

    print(
        f"Saved experimental movement report: {output}\n"
        f"Saved movement time series: {csv_output}\n"
        f"Estimated {len(report['windows'])} windows; "
        f"{sum(window['sudden_movement'] for window in report['windows'])} sudden-movement flags."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Log raw ESP-A CSI serial rows and timestamped block markers."""

from __future__ import annotations

import argparse
import csv
import re
import select
import sys
import threading
import time
import uuid
from pathlib import Path

import serial

N_SUBCARRIERS = 64
TIMESTAMP_MODULUS = 2**32
TEST1_BLOCKS = (
    ("empty", 180, "Leave the chair empty and clear everyone from the room."),
    ("p12_P0", 60, "Sit upright at P0; breathe at 12/min."),
    ("p18_P0", 60, "Stay at P0; breathe at 18/min."),
    ("p12_P0b", 60, "Stay at P0; return to 12/min."),
    ("p12_P1", 45, "Move chair +3 cm to P1; breathe at 12/min."),
    ("p12_P2", 45, "Move chair +6 cm to P2; breathe at 12/min."),
    ("p12_P3", 45, "Move chair +9 cm to P3; breathe at 12/min."),
)
PACKET_FIELDS = [
    "ts_us", "mac", "rssi", "rate", "sig_mode", "len",
    *(f"amp_{index:02d}" for index in range(N_SUBCARRIERS)),
    *(field for index in range(N_SUBCARRIERS)
      for field in (f"csi_i_{index:02d}", f"csi_q_{index:02d}")),
    "session_id", "host_time_s", "host_time_wall_s", "raw_line",
]
MARKER_FIELDS = [
    "event_id", "session_id", "host_time_s", "host_time_wall_s",
    "packet_count", "marker",
]


def parse_c_line(line: str) -> dict[str, int | str] | None:
    """Parse legacy magnitudes or interleaved signed I/Q values from a C row."""
    if not line.startswith("C,"):
        return None
    fields = line.split(",")
    if len(fields) < 7:
        raise ValueError("packet has fewer than 7 header fields")
    try:
        ts_us = int(fields[1])
        mac = fields[2].strip().lower()
        rssi, rate, sig_mode, length = map(int, fields[3:7])
        payload = [int(value) for value in fields[7:]]
    except ValueError as exc:
        raise ValueError(f"packet contains a non-integer field: {exc}") from exc
    if not 0 <= ts_us < TIMESTAMP_MODULUS:
        raise ValueError("ts_us is outside the uint32 range")
    if length < 2 or length > 2 * N_SUBCARRIERS or length % 2:
        raise ValueError("len must be an even number from 2 through 128")
    expected_amplitudes = length // 2
    has_iq = len(payload) == length
    if not has_iq and len(payload) != expected_amplitudes:
        raise ValueError(
            f"len={length} expects {expected_amplitudes} amplitudes or "
            f"{length} interleaved I/Q values; got {len(payload)} values"
        )
    amplitudes = [0] * N_SUBCARRIERS
    csi_i: list[int | str] = [""] * N_SUBCARRIERS
    csi_q: list[int | str] = [""] * N_SUBCARRIERS
    if has_iq:
        for index in range(expected_amplitudes):
            imag, real = payload[2 * index:2 * index + 2]
            csi_i[index] = real
            csi_q[index] = imag
            amplitudes[index] = int((real * real + imag * imag) ** 0.5 + 0.5)
    else:
        amplitudes[:expected_amplitudes] = payload
    return {
        "ts_us": ts_us,
        "mac": mac,
        "rssi": rssi,
        "rate": rate,
        "sig_mode": sig_mode,
        "len": length,
        **{f"amp_{index:02d}": value for index, value in enumerate(amplitudes)},
        **{
            field: value
            for index in range(N_SUBCARRIERS)
            for field, value in (
                (f"csi_i_{index:02d}", csi_i[index]),
                (f"csi_q_{index:02d}", csi_q[index]),
            )
        },
    }


def _session_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    if not name:
        raise ValueError("Session name must contain at least one letter or number")
    return name


def _args(test1_default: bool = False) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="ESP-A serial port, e.g. /dev/cu.usbserial-0001")
    parser.add_argument("session", nargs="?", default="session1",
                        help="filename stem (default: session1)")
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    if not test1_default:
        parser.add_argument(
            "--test1", action="store_true",
            help="run the guided empty/P0/position-scan schedule",
        )
    else:
        parser.set_defaults(test1=True)
    return parser.parse_args()


def _write_packets(port: serial.Serial, writer: csv.DictWriter, packet_handle,
                   session: str,
                   stop: threading.Event, state: dict[str, int | float | str | None]) -> None:
    last_status = time.monotonic()
    interval_packets = 0
    while not stop.is_set():
        try:
            raw = port.readline()
        except serial.SerialException as exc:
            state["error"] = f"Serial read failed: {exc}"
            stop.set()
            return
        host_mono = time.monotonic()
        host_wall = time.time()
        if not raw:
            continue
        line = raw.decode("ascii", errors="replace").strip()
        if not line:
            continue
        if line.startswith("#"):
            print(line, flush=True)
            station_match = re.search(r"\bstations\s*=\s*(\d+)", line, re.IGNORECASE)
            if station_match:
                state["stations"] = int(station_match.group(1))
            continue
        if not line.startswith("C,"):
            state["other_lines"] = int(state["other_lines"] or 0) + 1
            continue
        try:
            packet = parse_c_line(line)
        except ValueError as exc:
            state["malformed_packets"] = int(state["malformed_packets"] or 0) + 1
            print(f"WARNING: rejected malformed CSI row: {exc}", file=sys.stderr, flush=True)
            continue
        if packet is None:
            continue
        packet.update({
            "session_id": session,
            "host_time_s": f"{host_mono:.9f}",
            "host_time_wall_s": f"{host_wall:.6f}",
            "raw_line": line,
        })
        try:
            writer.writerow(packet)
            state["packet_count"] = int(state["packet_count"] or 0) + 1
            interval_packets += 1
            if host_mono - last_status >= 2.0:
                elapsed = host_mono - last_status
                print(
                    f"rows/s={interval_packets / elapsed:.1f} "
                    f"total={state['packet_count']} "
                    f"malformed={state['malformed_packets']}",
                    flush=True,
                )
                rate = interval_packets / elapsed
                state["rows_per_second"] = rate
                if int(state["stations"] or 0) == 1 and rate >= 90.0:
                    state["preflight_good_windows"] = (
                        int(state["preflight_good_windows"] or 0) + 1
                    )
                else:
                    state["preflight_good_windows"] = 0
                packet_handle.flush()
                interval_packets = 0
                last_status = host_mono
            elif int(state["packet_count"]) % 100 == 0:
                packet_handle.flush()
        except (OSError, csv.Error) as exc:
            state["error"] = f"Could not write packet CSV: {exc}"
            stop.set()
            return


def _wait_for_test1_preflight(stop: threading.Event,
                              state: dict[str, int | float | str | None]) -> bool:
    print(
        "TEST 1 link check: start the phone sender now. Waiting for stations=1 "
        "and >=90 rows/s for three consecutive 2-second intervals. Type q + Enter to abort.",
        flush=True,
    )
    while not stop.is_set():
        if int(state["preflight_good_windows"] or 0) >= 3:
            print(
                f"Link check passed: stations=1, rows/s={float(state['rows_per_second'] or 0):.1f}.",
                flush=True,
            )
            return True
        ready, _, _ = select.select([sys.stdin], [], [], 0.2)
        if ready:
            command = sys.stdin.readline()
            if command == "" or command.strip().lower() == "q":
                print("Aborting before test blocks.", flush=True)
                return False
            print(
                f"Waiting for link: stations={state['stations']}, "
                f"rows/s={float(state['rows_per_second'] or 0):.1f}",
                flush=True,
            )
    return False


def _run_test1_blocks(markers: csv.DictWriter, marker_handle, session: str,
                      stop: threading.Event,
                      state: dict[str, int | float | str | None]) -> None:
    print(
        "Guided Test 1 is ready. Ensure the empty-room baseline can begin, "
        "then press Enter for each prompt.",
        flush=True,
    )
    for label, duration_s, instruction in TEST1_BLOCKS:
        if stop.is_set():
            return
        print(
            f"\nNEXT BLOCK: {label} ({duration_s} seconds)\n{instruction}",
            flush=True,
        )
        if label.startswith("p12_") or label == "p18_P0":
            cadence = "5.0 s" if label.startswith("p12_") else "3.33 s"
            print(
                f"Start the metronome now ({cadence} between inhale-start clicks).",
                flush=True,
            )
        print(
            "When the block is physically ready, press Enter to mark its start.",
            flush=True,
        )
        while not stop.is_set():
            ready, _, _ = select.select([sys.stdin], [], [], 0.2)
            if not ready:
                continue
            command = sys.stdin.readline()
            if command == "":
                stop.set()
                return
            if command.strip().lower() == "q":
                print("Guided test cancelled.", flush=True)
                stop.set()
                return
            break
        if stop.is_set():
            return
        now_mono = time.monotonic()
        markers.writerow({
            "event_id": str(uuid.uuid4()),
            "session_id": session,
            "host_time_s": f"{now_mono:.9f}",
            "host_time_wall_s": f"{time.time():.6f}",
            "packet_count": int(state["packet_count"]),
            "marker": label,
        })
        marker_handle.flush()
        print(
            f"Marked {label!r} at packet {state['packet_count']}; "
            f"recording for {duration_s} seconds.",
            flush=True,
        )
        deadline = now_mono + duration_s
        next_countdown = duration_s - 15
        while not stop.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(1.0, remaining))
            remaining = deadline - time.monotonic()
            if remaining > 0 and remaining <= next_countdown:
                print(f"{label}: {remaining:.0f}s remaining", flush=True)
                next_countdown -= 15
    if not stop.is_set():
        stop.set()
        print("All Test 1 blocks complete; saving session files.", flush=True)


def main(test1_default: bool = False) -> int:
    args = _args(test1_default)
    if args.baud <= 0:
        raise SystemExit("--baud must be positive")
    try:
        session = _session_name(args.session)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    args.output_dir.mkdir(parents=True, exist_ok=True)
    packet_path = args.output_dir / f"{session}.csv"
    marker_path = args.output_dir / f"{session}.markers.csv"
    if packet_path.exists() or marker_path.exists():
        raise SystemExit(
            f"Refusing to overwrite an existing session file: {packet_path} or {marker_path}"
        )
    try:
        port = serial.Serial(args.port, args.baud, timeout=0.1)
    except serial.SerialException as exc:
        raise SystemExit(f"Could not open receiver port {args.port}: {exc}") from exc

    stop = threading.Event()
    state: dict[str, int | float | str | None] = {
        "packet_count": 0,
        "malformed_packets": 0,
        "other_lines": 0,
        "error": None,
        "stations": None,
        "rows_per_second": 0.0,
        "preflight_good_windows": 0,
    }
    try:
        with (
            packet_path.open("x", newline="", encoding="utf-8") as packet_handle,
            marker_path.open("x", newline="", encoding="utf-8") as marker_handle,
        ):
            packets = csv.DictWriter(packet_handle, fieldnames=PACKET_FIELDS)
            packets.writeheader()
            markers = csv.DictWriter(marker_handle, fieldnames=MARKER_FIELDS)
            markers.writeheader()
            packet_handle.flush()
            marker_handle.flush()
            reader = threading.Thread(
                target=_write_packets,
                args=(port, packets, packet_handle, session, stop, state),
                name="csi-serial-reader",
                daemon=True,
            )
            reader.start()
            print(
                f"Serial open on {args.port} at {args.baud} baud. "
                f"Logging {packet_path} and {marker_path}.",
                flush=True,
            )
            if not args.test1:
                print(
                    "Type a block label + Enter to mark it; type stop + Enter "
                    "to finish. Ctrl+C also stops cleanly.",
                    flush=True,
                )
            try:
                if args.test1:
                    if not _wait_for_test1_preflight(stop, state):
                        stop.set()
                    else:
                        _run_test1_blocks(
                            markers, marker_handle, session, stop, state
                        )
                while not stop.is_set():
                    ready, _, _ = select.select([sys.stdin], [], [], 0.2)
                    if not ready:
                        continue
                    label = sys.stdin.readline()
                    if label == "":
                        print("Input closed; stopping capture.", flush=True)
                        stop.set()
                        break
                    if label.strip().lower() == "stop":
                        stop.set()
                        break
                    label = label.strip()
                    if not label:
                        continue
                    now_mono = time.monotonic()
                    markers.writerow({
                        "event_id": str(uuid.uuid4()),
                        "session_id": session,
                        "host_time_s": f"{now_mono:.9f}",
                        "host_time_wall_s": f"{time.time():.6f}",
                        "packet_count": int(state["packet_count"]),
                        "marker": label,
                    })
                    marker_handle.flush()
                    print(
                        f"Marked {label!r} at packet {state['packet_count']}.",
                        flush=True,
                    )
            except KeyboardInterrupt:
                print("\nCtrl+C received; stopping capture.", flush=True)
                stop.set()
            finally:
                stop.set()
                reader.join(timeout=2.0)
                packet_handle.flush()
                marker_handle.flush()
    except FileExistsError as exc:
        raise SystemExit(f"Refusing to overwrite existing capture file: {exc.filename}") from exc
    finally:
        stop.set()
        port.close()

    print(
        f"Saved {state['packet_count']} packets, "
        f"{state['malformed_packets']} malformed rows, "
        f"{state['other_lines']} unrelated lines.",
        flush=True,
    )
    if state["error"]:
        raise SystemExit(str(state["error"]))
    print(f"Packet CSV: {packet_path}\nMarker CSV: {marker_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

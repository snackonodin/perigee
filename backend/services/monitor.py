"""On-demand Monitor sessions with the ESP receiver (INTEGRATION_PLAN.md §7, D1–D4).

Not always on: a session opens the serial port only when a person chooses Sleep analysis,
Measure heart rate or Measure breathing rate, and closes it when the session ends.

    connecting -> link_check -> calibrating (empty room, every session) -> running
               -> finalizing -> complete
    any active state -> link_error (port failed, link never passed, or packets stopped)
    stop() before running -> stopped; stop() while running -> finalize what was captured

One serial reader per device: only one session may be active at a time (MonitorBusy).
Each session writes, under DATA_DIR/monitor/<user_id>/<session_id>/:
    capture.csv   team-logger format (vendored waiwai1 logger PACKET_FIELDS); read-only after
    markers.csv   host_time_s, marker (calibration_start, run_start, run_end, ...)
    summary.json  the experimental session score (backend.services.session_scoring)

Nothing here feeds the nightly pipeline, the Context Engine, or the pet. Values are never
logged; only states and counts are.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import stat
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from backend.config import get_settings
from backend.services.session_scoring import score_session
from csi_core.config import CoreConfig, MonitorCfg, get_config

log = logging.getLogger(__name__)

Mode = Literal["sleep_analysis", "heart_rate", "breathing_rate"]
MODES: tuple[Mode, ...] = ("sleep_analysis", "heart_rate", "breathing_rate")
ACTIVE_STATES = {"connecting", "link_check", "calibrating", "running", "finalizing"}
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class Port(Protocol):
    def readline(self) -> bytes: ...
    def close(self) -> None: ...


class MonitorBusy(RuntimeError):
    """Another Monitor session is using the receiver."""


class MonitorUnavailable(RuntimeError):
    """No receiver configured (MONITOR_SERIAL_PORT is empty)."""


Analyze = Callable[[Path, float, datetime, str, CoreConfig], dict[str, list[dict[str, Any]]]]


def _logger_mod():
    from plugins.vendor.waiwai1 import logger

    return logger


# ---------------------------------------------------------------------------- link check


class LinkCheck:
    """Preflight: one station and >= min rows/s for N consecutive intervals."""

    def __init__(self, cfg: MonitorCfg) -> None:
        self.cfg = cfg
        self.good = 0
        self.rows_per_s = 0.0
        self._start: float | None = None
        self._count = 0
        self._macs: set[str] = set()

    @property
    def passed(self) -> bool:
        return self.good >= self.cfg.link_good_intervals

    def feed(self, t: float, mac: str | None) -> None:
        if self._start is None:
            self._start = t
        if mac is not None:
            self._count += 1
            self._macs.add(mac)
        span = t - self._start
        if span >= self.cfg.link_interval_s:
            self.rows_per_s = self._count / span
            ok = self.rows_per_s >= self.cfg.link_min_rows_per_s and len(self._macs) == 1
            self.good = self.good + 1 if ok else 0
            self._start, self._count, self._macs = t, 0, set()


# ---------------------------------------------------------------------------- analysis


def analyze_capture(
    path: Path, run_start_host_s: float, run_start_utc: datetime, session_id: str, cfg: CoreConfig
) -> dict[str, list[dict[str, Any]]]:
    """Run-phase readings on the run's clock: respiration, heart rate, motion acceleration."""
    from csi_core import breath, heart
    from csi_core.load import read_team_capture
    from csi_core.preprocess import clean
    from plugins.team_movement import acceleration_samples

    df = read_team_capture(path)
    df = df[df["host_time_utc"] >= run_start_utc].reset_index(drop=True)
    resp: list[dict[str, Any]] = []
    hearts: list[dict[str, Any]] = []
    if len(df) > 1:
        for w in breath.estimate_windows(clean(df, cfg), session_id, cfg):
            if w.rr_a is not None and not w.motion_flag:
                resp.append({"time_s": (w.t_end - run_start_utc).total_seconds(), "bpm": w.rr_a})
        for h in heart.estimate_session(df, session_id, cfg):
            if h.hr_bpm is not None:
                t = (h.t_end - run_start_utc).total_seconds()
                hearts.append({"time_s": t, "bpm": h.hr_bpm})
    return {
        "respiration": resp,
        "heart_rate": hearts,
        "motion": acceleration_samples(path, start_host_time_s=run_start_host_s),
    }


# ---------------------------------------------------------------------------- one session


class MonitorRun:
    def __init__(
        self,
        *,
        user_id: str,
        mode: Mode,
        out_root: Path,
        open_port: Callable[[], Port],
        analyze: Analyze = analyze_capture,
        cfg: MonitorCfg | None = None,
        core_cfg: CoreConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], float] = time.time,
        silence_s: float | None = None,
    ) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}")
        self.core_cfg = core_cfg or get_config()
        self.cfg = cfg or self.core_cfg.monitor
        if self.cfg is None:
            raise MonitorUnavailable("config.yaml has no monitor section")
        self.id = uuid.uuid4().hex
        self.user_id = user_id
        self.mode = mode
        self.dir = out_root / self.id
        self.state = "connecting"
        self.error: str | None = None
        self.created_at = datetime.fromtimestamp(wall(), UTC)
        self.summary: dict[str, Any] | None = None
        self.rows = 0
        self.rows_per_s = 0.0
        self.phase_ends_s: float | None = None
        self.host_s = 0.0
        self._open_port, self._analyze = open_port, analyze
        self._clock, self._wall = clock, wall
        self._silence_s = silence_s if silence_s is not None else 2 * self.cfg.link_interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- control
    def start(self) -> None:
        self._thread = threading.Thread(target=self.run_blocking, name=f"monitor-{self.id[:8]}",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def active(self) -> bool:
        return self.state in ACTIVE_STATES

    def status(self) -> dict[str, Any]:
        remaining = None
        if self.phase_ends_s is not None and self.state in ("calibrating", "running"):
            remaining = max(0.0, round(self.phase_ends_s - self.host_s, 1))
        return {
            "id": self.id,
            "mode": self.mode,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "remaining_s": remaining,
            "rows_per_s": round(self.rows_per_s, 1),
            "error": self.error,
        }

    # -- the loop
    def _set(self, state: str) -> None:
        self.state = state
        log.info("monitor %s %s", self.id[:8], state)

    def run_blocking(self) -> None:
        lg = _logger_mod()
        self.dir.mkdir(parents=True, exist_ok=False)
        try:
            port = self._open_port()
        except Exception:  # noqa: BLE001 - any open failure is a link error for the user
            self.error = "Could not open the receiver. Check that it is plugged in."
            self._set("link_error")
            return
        fields = [f for f in lg.PACKET_FIELDS if f != "raw_line"]
        run_start_host: float | None = None
        run_start_utc: datetime | None = None
        stopped_early = False
        try:
            with (self.dir / "capture.csv").open("w", newline="") as fh, \
                 (self.dir / "markers.csv").open("w", newline="") as mh:
                writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                markers = csv.writer(mh)
                markers.writerow(["host_time_s", "marker"])
                t0 = self._clock()
                last_packet = 0.0
                link = LinkCheck(self.cfg)
                self._set("link_check")

                def mark(name: str) -> None:
                    markers.writerow([f"{self.host_s:.6f}", name])

                while True:
                    if self._stop.is_set():
                        if self.state == "running":
                            stopped_early = True
                            mark("run_end")
                            break
                        mark("stopped")
                        self._set("stopped")
                        return
                    raw = port.readline()
                    now = self._clock()
                    self.host_s = now - t0
                    mac = None
                    if raw:
                        line = raw.decode("ascii", errors="replace").strip()
                        try:
                            row = lg.parse_c_line(line)
                        except ValueError:
                            row = None
                        if row is not None:
                            mac = str(row["mac"])
                            row.update(session_id=self.id, host_time_s=f"{self.host_s:.6f}",
                                       host_time_wall_s=f"{self._wall():.6f}")
                            writer.writerow(row)
                            self.rows += 1
                            last_packet = self.host_s
                    if self.state == "link_check":
                        link.feed(self.host_s, mac)
                        self.rows_per_s = link.rows_per_s
                        if link.passed:
                            mark("calibration_start")
                            self.phase_ends_s = self.host_s + self.cfg.calibration_s
                            self._set("calibrating")
                        elif self.host_s >= self.cfg.link_timeout_s:
                            self.error = ("The receiver signal was too weak or mixed. "
                                          "Move closer and try again.")
                            mark("link_failed")
                            self._set("link_error")
                            return
                        continue
                    if self.host_s - last_packet > self._silence_s:
                        self.error = "The receiver stopped sending data. Partial capture kept."
                        mark("link_lost")
                        self._set("link_error")
                        return
                    if self.state == "calibrating" and self.host_s >= (self.phase_ends_s or 0):
                        mark("calibration_end")
                        mark("run_start")
                        run_start_host = self.host_s
                        run_start_utc = datetime.fromtimestamp(self._wall(), UTC)
                        self.phase_ends_s = self.host_s + getattr(self.cfg.duration_s, self.mode)
                        self._set("running")
                    elif self.state == "running" and self.host_s >= (self.phase_ends_s or 0):
                        mark("run_end")
                        break
        finally:
            try:
                port.close()
            except Exception:  # noqa: BLE001
                log.warning("monitor %s: port close failed", self.id[:8])
        self._finalize(run_start_host or 0.0, run_start_utc or self.created_at, stopped_early)

    def _finalize(
        self, run_start_host: float, run_start_utc: datetime, stopped_early: bool
    ) -> None:
        self._set("finalizing")
        capture = self.dir / "capture.csv"
        try:
            readings = self._analyze(capture, run_start_host, run_start_utc, self.id, self.core_cfg)
        except Exception:  # noqa: BLE001 - estimator failure must not lose the capture
            log.exception("monitor %s: analysis failed", self.id[:8])
            readings = {"respiration": [], "heart_rate": [], "motion": []}
        summary = score_session(
            respiration_bpm=readings.get("respiration"),
            heart_rate_bpm=readings.get("heart_rate"),
            motion_samples=readings.get("motion"),
            cfg=self.core_cfg.session_scoring,
        )
        if self.mode != "sleep_analysis":
            summary["sleep_score"] = None
            summary["score_status"] = "not_applicable"
        summary.update(
            id=self.id,
            mode=self.mode,
            created_at=self.created_at.isoformat(),
            run_seconds=round(max(0.0, self.host_s - run_start_host), 1),
            stopped_early=stopped_early,
            calibration={"kind": "empty_room", "seconds": self.cfg.calibration_s},
            rows=self.rows,
        )
        tmp = self.dir / "summary.json.tmp"
        tmp.write_text(json.dumps(summary, indent=2))
        os.replace(tmp, self.dir / "summary.json")
        for p in (capture, self.dir / "markers.csv"):
            p.chmod(stat.S_IRUSR | stat.S_IRGRP)
        self.summary = summary
        self._set("complete")


# ---------------------------------------------------------------------------- registry


_LOCK = threading.Lock()
_RUNS: dict[str, MonitorRun] = {}


def runs_root(user_id: str) -> Path:
    if not _ID.match(user_id):
        raise ValueError("bad user id")
    return get_settings().data_dir / "monitor" / user_id


def _default_open_port(name: str, baud: int) -> Callable[[], Port]:
    def opener() -> Port:
        import serial

        return serial.Serial(name, baud, timeout=0.1)

    return opener


def start(
    user_id: str,
    mode: Mode,
    *,
    open_port: Callable[[], Port] | None = None,
    background: bool = True,
    **kwargs: Any,
) -> MonitorRun:
    """Start a session. Raises MonitorBusy if the receiver is in use, MonitorUnavailable if
    no receiver is configured."""
    with _LOCK:
        if any(r.active for r in _RUNS.values()):
            raise MonitorBusy("the receiver is in use")
        if open_port is None:
            cfg = get_config().monitor
            port_name = get_settings().monitor_serial_port
            if cfg is None or not port_name:
                raise MonitorUnavailable("no receiver configured (MONITOR_SERIAL_PORT)")
            open_port = _default_open_port(port_name, cfg.baud)
        run = MonitorRun(user_id=user_id, mode=mode, out_root=runs_root(user_id),
                         open_port=open_port, **kwargs)
        _RUNS[run.id] = run
    if background:
        run.start()
    else:
        run.run_blocking()
    return run


def modes(cfg: MonitorCfg | None = None) -> list[dict[str, Any]]:
    """Per-mode timing for the UI (room check + session), straight from config."""
    cfg = cfg or get_config().monitor
    if cfg is None:
        return []
    out = []
    for mode in MODES:
        duration = float(getattr(cfg.duration_s, mode))
        out.append({"mode": mode, "calibration_s": float(cfg.calibration_s),
                    "duration_s": duration, "total_s": float(cfg.calibration_s) + duration})
    return out


def _read_summary(user_id: str, run_id: str) -> dict[str, Any] | None:
    if not _ID.match(run_id):
        return None
    p = runs_root(user_id) / run_id / "summary.json"
    return json.loads(p.read_text()) if p.is_file() else None


def get(user_id: str, run_id: str) -> dict[str, Any] | None:
    """Status (and summary when complete) of the caller's own session, else None."""
    run = _RUNS.get(run_id)
    if run is not None:
        if run.user_id != user_id:
            return None
        out = run.status()
        out["summary"] = run.summary
        return out
    summary = _read_summary(user_id, run_id)
    if summary is None:
        return None
    return {"id": run_id, "mode": summary["mode"], "state": "complete",
            "created_at": summary["created_at"], "remaining_s": None, "rows_per_s": None,
            "error": None, "summary": summary}


def stop(user_id: str, run_id: str) -> bool:
    run = _RUNS.get(run_id)
    if run is None or run.user_id != user_id or not run.active:
        return False
    run.stop()
    return True


def list_runs(user_id: str) -> list[dict[str, Any]]:
    root = runs_root(user_id)
    out = []
    if root.is_dir():
        for d in root.iterdir():
            item = get(user_id, d.name)
            if item is not None:
                out.append(item)
    return sorted(out, key=lambda r: r["created_at"], reverse=True)


# ---------------------------------------------------------------------------- display (D1, D4)


def public_view(item: dict[str, Any], show_rates: bool = False) -> dict[str, Any]:
    """Flags by default; numbers only when asked (show_rates) or for the measure the person
    chose to measure (heart_rate / breathing_rate modes)."""
    item = json.loads(json.dumps(item))
    summary = item.get("summary")
    if not summary:
        return item
    voluntary = {"heart_rate": "heart_rate", "breathing_rate": "respiration"}.get(item["mode"])
    for measure in ("respiration", "heart_rate"):
        block = summary.get(measure)
        if not block:
            continue
        visible = show_rates or measure == voluntary
        block["values_shown"] = visible
        if not visible:
            block["readings"] = [
                {"time_s": r["time_s"], "position": r["position"]} for r in block["readings"]
            ]
            block.pop("reference_range", None)
            block.pop("mean_deviation_below", None)
            block.pop("mean_deviation_above", None)
    return item

"""On-demand Monitor sessions: state machine, link check, calibration, isolation, display."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services import monitor as mon
from csi_core.config import MonitorCfg, MonitorDurationsCfg, get_config

CFG = MonitorCfg(
    baud=921600, link_min_rows_per_s=90, link_interval_s=2, link_good_intervals=3,
    link_timeout_s=10, calibration_s=3,
    duration_s=MonitorDurationsCfg(sleep_analysis=4, heart_rate=2, breathing_rate=2),
)
MAC_A, MAC_B = "aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class FakePort:
    """Emits one packet per readline at `hz`, advancing the fake clock. Optional MAC mix,
    a silence window, and a stop hook."""

    def __init__(self, clock: FakeClock, hz: float = 100, macs=(MAC_A,), silent_after=None,
                 on_read=None) -> None:
        self.clock, self.dt, self.macs = clock, 1.0 / hz, macs
        self.n, self.closed = 0, False
        self.silent_after, self.on_read = silent_after, on_read

    def readline(self) -> bytes:
        self.clock.t += self.dt
        self.n += 1
        if self.on_read:
            self.on_read(self)
        if self.silent_after is not None and self.clock.t > self.silent_after:
            return b""
        mac = self.macs[self.n % len(self.macs)]
        return f"C,{self.n * 10000},{mac},-40,11,0,4,3,4,5,6\n".encode()

    def close(self) -> None:
        self.closed = True


def fake_analyze(calls: list):
    def analyze(path, run_start_host_s, run_start_utc, session_id, cfg):
        calls.append((path, run_start_host_s))
        return {
            "respiration": [{"time_s": 30, "bpm": 15.0}, {"time_s": 60, "bpm": 25.0}],
            "heart_rate": [{"time_s": 15, "bpm": 72.0}],
            "motion": [{"time_s": float(i), "acceleration_m_s2": 0.01} for i in range(20)],
        }
    return analyze


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(mon, "runs_root", lambda uid: tmp_path / "monitor" / uid)
    monkeypatch.setattr(mon, "_RUNS", {})
    yield


def _start(user="userA", mode="sleep_analysis", port_kwargs=None, calls=None):
    clock = FakeClock()
    port = FakePort(clock, **(port_kwargs or {}))
    run = mon.start(user, mode, open_port=lambda: port, background=False, cfg=CFG,
                    clock=clock, wall=lambda: 1_800_000_000 + clock.t,
                    analyze=fake_analyze(calls if calls is not None else []))
    return run, port


def _markers(run) -> list[str]:
    lines = (run.dir / "markers.csv").read_text().splitlines()[1:]
    return [line.split(",")[1] for line in lines]


def test_happy_path_link_check_then_calibration_then_run_then_complete():
    calls: list = []
    run, port = _start(calls=calls)
    assert run.state == "complete" and port.closed
    assert _markers(run) == ["calibration_start", "calibration_end", "run_start", "run_end"]
    summary = json.loads((run.dir / "summary.json").read_text())
    assert summary["calibration"] == {"kind": "empty_room", "seconds": 3}
    assert summary["respiration"]["counts"] == {"below": 0, "in": 1, "above": 1}
    assert summary["sleep_score"] is not None
    # analysis sees only the run phase: it starts after link check (>=6 s) + calibration (3 s)
    assert calls and calls[0][1] >= 9.0
    assert 3.9 <= summary["run_seconds"] <= 4.1
    assert run.rows > 1000  # ~100 rows/s for ~13 s
    header = (run.dir / "capture.csv").read_text().splitlines()[0]
    assert "raw_line" not in header and "host_time_s" in header


def test_calibration_runs_every_session():
    first, _ = _start()
    second, _ = _start()
    assert "calibration_start" in _markers(first) and "calibration_start" in _markers(second)


def test_low_packet_rate_never_passes_link_check():
    run, port = _start(port_kwargs={"hz": 50})
    assert run.state == "link_error" and port.closed
    assert "calibration_start" not in _markers(run)
    assert not (run.dir / "summary.json").exists()


def test_two_stations_fail_the_link_check():
    run, _ = _start(port_kwargs={"macs": (MAC_A, MAC_B)})
    assert run.state == "link_error"


def test_link_lost_during_run_keeps_partial_capture():
    run, _ = _start(port_kwargs={"silent_after": 7.0})
    assert run.state == "link_error"
    assert "link_lost" in _markers(run)
    assert (run.dir / "capture.csv").stat().st_size > 0


def test_stop_while_running_finalizes_what_was_captured():
    holder = {}

    def on_read(port):
        r = holder.get("run")
        if r is not None and r.state == "running" and r.host_s > r.phase_ends_s - 2.5:
            r.stop()

    clock = FakeClock()
    port = FakePort(clock, on_read=on_read)
    run = mon.MonitorRun(user_id="userA", mode="sleep_analysis", out_root=mon.runs_root("userA"),
                         open_port=lambda: port, analyze=fake_analyze([]), cfg=CFG,
                         clock=clock, wall=lambda: clock.t)
    holder["run"] = run
    run.run_blocking()
    assert run.state == "complete" and run.summary["stopped_early"] is True


def test_stop_before_running_ends_without_summary():
    def on_read(port):
        if port.clock.t > 1.0:
            holder["run"].stop()

    holder = {}
    clock = FakeClock()
    port = FakePort(clock, on_read=on_read)
    run = mon.MonitorRun(user_id="userA", mode="heart_rate", out_root=mon.runs_root("userA"),
                         open_port=lambda: port, analyze=fake_analyze([]), cfg=CFG,
                         clock=clock, wall=lambda: clock.t)
    holder["run"] = run
    run.run_blocking()
    assert run.state == "stopped" and not (run.dir / "summary.json").exists()


def test_port_open_failure_is_a_link_error():
    def boom():
        raise OSError("no such device")

    run = mon.start("userA", "sleep_analysis", open_port=boom, background=False, cfg=CFG)
    assert run.state == "link_error" and "receiver" in run.error


def test_only_one_session_at_a_time(monkeypatch):
    clock = FakeClock()
    busy = mon.MonitorRun(user_id="userA", mode="sleep_analysis", out_root=Path("/nonexistent"),
                          open_port=lambda: FakePort(clock), cfg=CFG)
    busy.state = "running"
    mon._RUNS[busy.id] = busy
    with pytest.raises(mon.MonitorBusy):
        _start(user="userB")


def test_no_receiver_configured(monkeypatch):
    class S:
        monitor_serial_port = ""
    monkeypatch.setattr(mon, "get_settings", lambda: S())
    with pytest.raises(mon.MonitorUnavailable):
        mon.start("userA", "heart_rate", background=False)


def test_user_b_cannot_read_stop_or_list_user_a_sessions():
    run, _ = _start(user="userA")
    assert mon.get("userA", run.id) is not None
    assert mon.get("userB", run.id) is None
    assert mon.stop("userB", run.id) is False
    assert mon.list_runs("userB") == []
    mon._RUNS.clear()  # after a restart, the summary on disk is still user-scoped
    assert mon.get("userA", run.id)["summary"]["id"] == run.id
    assert mon.get("userB", run.id) is None


def test_measure_modes_have_no_session_score():
    run, _ = _start(mode="heart_rate")
    assert run.summary["sleep_score"] is None and run.summary["score_status"] == "not_applicable"


def test_display_shows_flags_by_default_and_values_on_request():
    run, _ = _start(mode="sleep_analysis")
    item = mon.get("userA", run.id)
    hidden = mon.public_view(item)
    rr = hidden["summary"]["respiration"]
    assert rr["flag"] == "above_range" and rr["values_shown"] is False
    assert all("value" not in r for r in rr["readings"])
    shown = mon.public_view(item, show_rates=True)
    assert shown["summary"]["respiration"]["readings"][0]["value"] == 15.0


def test_voluntary_measure_shows_only_that_measure():
    run, _ = _start(mode="heart_rate")
    view = mon.public_view(mon.get("userA", run.id))
    assert view["summary"]["heart_rate"]["values_shown"] is True
    assert view["summary"]["respiration"]["values_shown"] is False


def test_repo_monitor_config_loads():
    cfg = get_config().monitor
    assert cfg is not None and cfg.calibration_s > 0


def test_real_analysis_on_team_iq_fixture():
    """analyze_capture runs the real estimators and the vendored movement code end to end."""
    from datetime import UTC, datetime

    import pandas as pd

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "team_iq_empty_30s.csv"
    t0 = float(pd.read_csv(fixture, usecols=["host_time_wall_s"]).iloc[0, 0])
    out = mon.analyze_capture(fixture, 0.0, datetime.fromtimestamp(t0, UTC), "s1", get_config())
    assert set(out) == {"respiration", "heart_rate", "motion"}
    assert len(out["motion"]) > 0  # 30 s of I/Q -> Doppler windows
    assert all({"time_s", "acceleration_m_s2"} <= set(m) for m in out["motion"])


def test_modes_report_config_timings():
    out = {m["mode"]: m for m in mon.modes(CFG)}
    assert set(out) == set(mon.MODES)
    assert out["sleep_analysis"] == {"mode": "sleep_analysis", "calibration_s": 3.0,
                                     "duration_s": 4.0, "total_s": 7.0}

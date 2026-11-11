"""Team logger format: auto-detected, filtered like the team's load_capture.

All data here is randomly generated; no real capture is used.
"""

import json

import numpy as np
import pandas as pd
import pytest

from csi_core.load import capture_format, capture_stats, read_rotating

PHONE = "aabbccddeeff"
OTHER = "112233445566"


def _team_csv(path, n=400, seed=0, fs=100.0, t0=1_794_226_315.5, wrap=True):
    rng = np.random.default_rng(seed)
    t = np.arange(n) / fs
    ts = ((2**32 - 1_000_000 if wrap else 5_000) + np.round(t * 1e6)).astype(np.int64) % 2**32
    rows = {
        "ts_us": ts,
        "mac": PHONE,
        "rssi": -58,
        "rate": 12,
        "sig_mode": 0,
        "len": 128,
    }
    df = pd.DataFrame(rows)
    for k in range(64):
        df[f"amp_{k:02d}"] = 0.0 if k >= 52 else rng.uniform(5, 30, n)
    df["session_id"] = "s"
    df["host_time_s"] = 63100.0 + t
    df["host_time_wall_s"] = t0 + t
    df["raw_line"] = "C,..."
    # noise rows the team loader drops: other MAC, HT packet, bad length
    bad = df.iloc[:3].copy()
    bad.loc[bad.index[0], "mac"] = OTHER
    bad.loc[bad.index[1], "sig_mode"] = 1
    bad.loc[bad.index[2], "len"] = 200
    pd.concat([df, bad]).to_csv(path, index=False)
    return path


def test_format_detected_by_header(tmp_path) -> None:
    p = _team_csv(tmp_path / "cap.csv")
    assert capture_format(list(pd.read_csv(p, nrows=0).columns)) == "team"
    assert capture_format(["host_time_utc", "ts_us", "rate", "a0"]) == "synth"
    with pytest.raises(ValueError):
        capture_format(["foo"])


def test_team_capture_maps_to_our_frame(tmp_path, cfg) -> None:
    df = read_rotating([_team_csv(tmp_path / "cap.csv")])
    assert list(df.columns[:3]) == ["host_time_utc", "ts_us", "rate"]
    assert list(df.columns[3:]) == [f"a{k}" for k in range(52)]  # inactive 52..63 dropped
    assert len(df) == 400  # the 3 noise rows are filtered out
    assert "mac" not in df.columns
    assert str(df["host_time_utc"].dt.tz) == "UTC"
    assert df["host_time_utc"].iloc[0] == pd.Timestamp(1_794_226_315.5, unit="s", tz="UTC")
    s = capture_stats(df, cfg)
    assert s.timestamp_wraps == 1 and s.mean_rows_per_s == pytest.approx(100, rel=0.01)


def test_sidecar_phone_mac_wins(tmp_path) -> None:
    p = _team_csv(tmp_path / "cap.csv")
    (tmp_path / "cap.json").write_text(json.dumps({"phone_mac": "11:22:33:44:55:66"}))
    assert len(read_rotating([p])) == 1  # only the single OTHER-mac row remains


def test_team_capture_runs_through_clean_and_windows(tmp_path, cfg) -> None:
    from csi_core.breath import estimate_windows
    from csi_core.preprocess import clean

    df = read_rotating([_team_csv(tmp_path / "cap.csv", n=100 * 150, wrap=False)])
    ws = estimate_windows(clean(df, cfg), "s", cfg)
    assert len(ws) >= 3 and all(w.t_start.tzinfo is not None for w in ws)

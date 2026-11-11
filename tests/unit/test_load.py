import numpy as np
import pandas as pd
import pytest

from csi_core.load import capture_stats, read_rotating


def _csi(paths):
    return [p for p in paths if p.name.startswith("csi_")]


def test_read_rotating_columns_and_order(night_dir) -> None:
    _, paths = night_dir
    df = read_rotating(list(reversed(_csi(paths))))  # order independent
    assert list(df.columns[:3]) == ["host_time_utc", "ts_us", "rate"]
    assert list(df.columns[3:]) == [f"a{k}" for k in range(12)]
    assert str(df["host_time_utc"].dt.tz) == "UTC"
    assert df["host_time_utc"].is_monotonic_increasing
    assert df["ts_us"].dtype == np.int64


def test_capture_stats_on_synth(night_dir, cfg) -> None:
    _, paths = night_dir
    s = capture_stats(read_rotating(_csi(paths)), cfg)
    assert s.timestamp_wraps == 1
    assert s.duration_s == pytest.approx(600, abs=1)
    assert s.mean_rows_per_s == pytest.approx(20 * 0.995, rel=0.01)
    assert s.max_gap_s >= 0.1  # dropped packets at 20 Hz leave >=100 ms gaps
    assert s.gaps_over_50ms > 0
    assert s.rate_changes == 2


def test_capture_stats_handcrafted(cfg) -> None:
    df = pd.DataFrame(
        {
            "host_time_utc": pd.date_range("2026-01-01", periods=5, freq="10ms", tz="UTC"),
            "ts_us": [2**32 - 20_000, 2**32 - 10_000, 0, 100_000, 110_000],
            "rate": [11, 11, 54, 54, 11],
        }
    )
    s = capture_stats(df, cfg)
    assert s.rows == 5 and s.timestamp_wraps == 1 and s.rate_changes == 2
    assert s.duration_s == pytest.approx(0.13)
    assert s.max_gap_s == pytest.approx(0.1)
    assert s.gaps_over_50ms == 1


def test_capture_stats_empty(cfg) -> None:
    df = pd.DataFrame({"host_time_utc": [], "ts_us": [], "rate": []})
    assert capture_stats(df, cfg).rows == 0

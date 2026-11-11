"""Fixtures: a throwaway DATA_DIR and SQLite DB per test."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from backend import db as db_mod
from backend.config import get_settings


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    d = tmp_path / "astro-data"
    d.mkdir()
    monkeypatch.setenv("DATA_DIR", str(d))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{d / 'db' / 'astro.db'}")
    get_settings.cache_clear()
    yield d
    get_settings.cache_clear()


@pytest.fixture
def engine(data_dir: Path) -> Iterator[Engine]:
    eng = db_mod.init_db()
    yield eng
    eng.dispose()
    db_mod.SessionLocal.configure(bind=None)


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with db_mod.SessionLocal() as s:
        yield s


# ----------------------------------------------------------------- capture fixture
# Same layout as csi_core.synth.synth_night (interfaces.md capture format):
# hourly csi_HH.csv.gz with header host_time_utc,ts_us,rate,a0..a51, meta.json and
# markers.csv. 10 min at 20 Hz from 22:55Z => 2 hourly files and 1 ts_us wrap.
# The coordinator swaps this for the real synth at merge.

CAPTURE_START = datetime(2026, 11, 10, 22, 55, tzinfo=UTC)
CAPTURE_FS = 20.0
CAPTURE_MINUTES = 10
N_SUB = 52


def write_capture(out_dir: Path, *, seed: int = 7, start: datetime = CAPTURE_START) -> Path:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = int(CAPTURE_MINUTES * 60 * CAPTURE_FS)
    t_s = np.arange(n) / CAPTURE_FS
    t_s = np.delete(t_s, [100, 101, 102])  # a dropped-packet gap (> 50 ms)
    period = 1 << 32
    start_counter = period - int(t_s[-1] * 1e6 / 2)  # wrap half-way through
    ts_us = (start_counter + np.round(t_s * 1e6).astype(np.int64)) % period
    rate = np.full(t_s.size, 11)
    rate[2000:2020] = 54  # two rate changes
    breath = np.sin(2 * np.pi * 15 / 60 * t_s)
    amps = 20 + np.outer(breath, rng.uniform(-1, 1, N_SUB)) + rng.normal(0, 0.3, (t_s.size, N_SUB))
    host = pd.DatetimeIndex(start + pd.to_timedelta(t_s, unit="s"))
    df = pd.DataFrame(
        {"host_time_utc": host.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "ts_us": ts_us, "rate": rate}
    )
    df = pd.concat(
        [df, pd.DataFrame(np.round(amps, 3), columns=[f"a{k}" for k in range(N_SUB)])], axis=1
    )
    hour = host.floor("h")
    for h in hour.unique():
        df[hour == h].to_csv(
            out_dir / f"csi_{h.hour:02d}.csv.gz", index=False,
            compression={"method": "gzip", "mtime": 0},
        )  # fmt: skip
    end = start + timedelta(seconds=float(t_s[-1]))
    meta = {
        "start_utc": start.isoformat().replace("+00:00", "Z"),
        "end_utc": end.isoformat().replace("+00:00", "Z"),
        "condition": "synthetic_night", "distance_m": None, "posture": None,
        "paced_bpm": 15.0, "reference_device": None, "room_notes": f"fixture seed={seed}",
        "phone_model": None, "source_kind": "synthetic",
    }  # fmt: skip
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True))
    mk = pd.DataFrame(
        {
            "host_time_utc": [
                (start + timedelta(seconds=s)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                for s in (60, 75, 420, 480)
            ],
            "label": ["motion_start", "motion_end", "absent_start", "absent_end"],
        }
    )
    mk.to_csv(out_dir / "markers.csv", index=False)
    return out_dir


@pytest.fixture(scope="session")
def _capture_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_capture(tmp_path_factory.mktemp("capture-template") / "capture")


@pytest.fixture
def capture_dir(_capture_template: Path, tmp_path: Path) -> Path:
    """A fresh, writable copy per test (tests may break it on purpose)."""
    return Path(shutil.copytree(_capture_template, tmp_path / "capture"))

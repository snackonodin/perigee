import gzip
import hashlib
import json
from datetime import UTC, datetime

import pandas as pd

from backend.schemas.contracts import SessionRecord
from csi_core.synth import synth_night
from csi_core.timebase import count_wraps


def test_writes_capture_format(night_dir) -> None:
    d, paths = night_dir
    names = [p.name for p in paths]
    assert names == ["csi_22.csv.gz", "csi_23.csv.gz", "meta.json", "markers.csv"]
    with gzip.open(d / "csi_22.csv.gz", "rt") as fh:
        header = fh.readline().strip().split(",")
    assert header == ["host_time_utc", "ts_us", "rate"] + [f"a{k}" for k in range(12)]
    df = pd.read_csv(d / "csi_23.csv.gz")
    assert df["host_time_utc"].str.endswith("Z").all()
    assert df["ts_us"].between(0, 2**32 - 1).all()


def test_short_fixture_crosses_a_wrap(night_dir) -> None:
    d, paths = night_dir
    ts = pd.concat(pd.read_csv(p)["ts_us"] for p in paths if p.name.startswith("csi_"))
    assert count_wraps(ts.to_numpy()) == 1


def test_meta_is_session_metadata(night_dir) -> None:
    d, _ = night_dir
    meta = json.loads((d / "meta.json").read_text())
    assert "id" not in meta and "user_id" not in meta
    rec = SessionRecord(user_id="u", **meta)
    assert rec.source_kind.value == "synthetic"
    assert rec.paced_bpm == 15.0


def test_markers(night_dir) -> None:
    d, _ = night_dir
    mk = pd.read_csv(d / "markers.csv")
    assert list(mk.columns) == ["host_time_utc", "label"]
    assert (mk["label"] == "absent_start").sum() == 1
    assert (mk["label"] == "motion_start").sum() == 2


def test_deterministic(tmp_path) -> None:
    kw = dict(
        start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        hours=1 / 60,
        rr_bpm=lambda t: 12 + t / 60,
        fs=20.0,
        n_sub=4,
        motion_bursts=1,
        seed=3,
    )
    a = synth_night(tmp_path / "a", **kw)
    b = synth_night(tmp_path / "b", **kw)
    for pa, pb in zip(a, b, strict=True):
        assert hashlib.sha256(pa.read_bytes()).digest() == hashlib.sha256(pb.read_bytes()).digest()

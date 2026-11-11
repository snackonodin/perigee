"""Convert a team logger capture (waiwai1 format) into our capture folder.

Our ingestion takes hourly ``csi_HH.csv.gz`` + ``meta.json`` (+ ``markers.csv``)
(docs/interfaces.md). This writes that folder from one team CSV, read with
csi_core.load (same filtering as the team loader). Signed I/Q columns are kept as
iK/qK so the I/Q heart path still works after ingest. The phone MAC and the raw
serial line are never written. Source files are only read.

    folder = to_capture_folder(Path("trial.csv"), out_dir)
    ingestion.ingest_session(db, user_id, folder)
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.schemas.contracts import Posture
from csi_core.load import read_team_capture

# Sidecar keys copied into meta.json (SessionRecord metadata). Free-text fields
# (room_notes, operator, helper ids) and device identifiers are deliberately omitted.
_NUMERIC = {"distance_m": "distance_m", "paced_rate_bpm": "paced_bpm"}


def _meta_from_sidecar(sidecar: dict, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    meta: dict = {
        "start_utc": start.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "end_utc": end.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "condition": str(sidecar["condition"])[:64] if sidecar.get("condition") else None,
        "distance_m": None,
        "posture": None,
        "paced_bpm": None,
        "reference_device": None,
        "room_notes": None,
        "phone_model": None,
        "source_kind": "csi",
    }
    for src, dst in _NUMERIC.items():
        v = sidecar.get(src)
        if isinstance(v, int | float) and not isinstance(v, bool):
            meta[dst] = float(v)
    if sidecar.get("posture") in {p.value for p in Posture}:
        meta["posture"] = sidecar["posture"]
    return meta


def to_capture_folder(src: Path, out_dir: Path, *, phone_mac: str | None = None) -> Path:
    """Write ``out_dir`` (created) as an ingestable capture folder; return it."""
    src, out_dir = Path(src), Path(out_dir)
    df = read_team_capture(src, phone_mac=phone_mac)
    if len(df) < 2:
        raise ValueError(f"{src.name}: fewer than two usable packets")
    out_dir.mkdir(parents=True, exist_ok=False)
    times = df["host_time_utc"]
    hour = times.dt.floor("h")
    for h in hour.unique():
        part = df[hour == h].copy()
        part["host_time_utc"] = part["host_time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        part.to_csv(
            out_dir / f"csi_{h.hour:02d}.csv.gz",
            index=False,
            compression={"method": "gzip", "mtime": 0},
        )
    sidecar_path = src.with_suffix(".json")
    sidecar = json.loads(sidecar_path.read_text()) if sidecar_path.is_file() else {}
    meta = _meta_from_sidecar(sidecar, times.iloc[0], times.iloc[-1])
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True))
    return out_dir

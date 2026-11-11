"""Ingest one capture folder into DATA_DIR and the DB (FR1, FR4).

A capture folder holds hourly ``csi_HH.csv.gz`` files, ``meta.json`` (SessionRecord
metadata without id/user_id) and optionally ``markers.csv`` (host_time_utc,label).

Steps:
1. Hash every file (sha256). The session hash is the sha256 of the sorted CSI file
   hashes. If this user already has a session with that hash, return it unchanged
   (idempotent). If only some files are known, refuse: that is an overlapping or
   edited capture and needs a human decision.
2. Validate meta.json and markers.csv, and compute capture stats.
3. Copy the files into DATA_DIR/raw/<session_id>/ BEFORE the DB transaction
   (staged in a temp dir, hashes re-checked, then renamed into place and made
   read-only). Source files are only read, never modified.
4. Insert the sessions, raw_files and markers rows in one transaction. If it fails,
   the copied folder is removed.

Paths stored in the DB are relative to DATA_DIR, so a DB moved to another device
with its DATA_DIR stays valid.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models import CaptureSession, Marker, RawFile, User, scoped
from backend.schemas.contracts import (
    CaptureStats,
    MarkerRecord,
    RawFileRecord,
    SessionRecord,
    new_id,
)
from csi_core.config import CoreConfig, get_config

log = logging.getLogger(__name__)

CSI_GLOB = "csi_*.csv.gz"
META_NAME = "meta.json"
MARKERS_NAME = "markers.csv"
_CHUNK = 1 << 20


class IngestError(ValueError):
    """The folder cannot be ingested as-is (bad metadata, overlap, missing files)."""


@dataclass(frozen=True)
class _SrcFile:
    src: Path
    name: str
    kind: str
    sha256: str
    size: int
    rows: int = 0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def session_hash(csi_hashes: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(csi_hashes)).encode()).hexdigest()


def raw_root() -> Path:
    return get_settings().data_dir / "raw"


# ----------------------------------------------------------------- capture stats
# STUB until feat/csi-core merges. Then replace the body of compute_capture_stats with:
#     from csi_core.load import capture_stats, read_rotating
#     return capture_stats(read_rotating(files), cfg)
# Semantics match csi_core (wrap = drop larger than half the counter range).


def _read_csi(files: list[Path]) -> pd.DataFrame:
    frames = []
    for p in files:
        df = pd.read_csv(p, compression="gzip")
        missing = {"host_time_utc", "ts_us", "rate"} - set(df.columns)
        if missing:
            raise IngestError(f"{p.name}: missing columns {sorted(missing)}")
        if len(df):
            df["host_time_utc"] = pd.to_datetime(df["host_time_utc"], utc=True, format="ISO8601")
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["host_time_utc", "ts_us", "rate"])
    frames.sort(key=lambda f: f["host_time_utc"].iloc[0])
    return pd.concat(frames, ignore_index=True)


def compute_capture_stats(files: list[Path], cfg: CoreConfig) -> CaptureStats:
    df = _read_csi(files)
    rows = int(len(df))
    if rows < 2:
        return CaptureStats(
            rows=rows, duration_s=0.0, mean_rows_per_s=0.0, max_gap_s=0.0,
            gaps_over_50ms=0, rate_changes=0, timestamp_wraps=0,
        )  # fmt: skip
    period = np.int64(1) << np.int64(cfg.capture.timestamp_bits)
    raw = df["ts_us"].to_numpy(dtype=np.int64)
    wrap_steps = np.diff(raw) < -(period // 2)
    t_us = raw + np.concatenate([[0], np.cumsum(wrap_steps)]).astype(np.int64) * period
    duration_s = max(float(t_us[-1] - t_us[0]) / 1e6, 0.0)
    gaps_s = np.diff(t_us) / 1e6
    rate = df["rate"].to_numpy()
    return CaptureStats(
        rows=rows,
        duration_s=duration_s,
        mean_rows_per_s=rows / duration_s if duration_s > 0 else 0.0,
        max_gap_s=max(float(gaps_s.max()), 0.0),
        gaps_over_50ms=int((gaps_s > cfg.capture.gap_threshold_s).sum()),
        rate_changes=int((rate[1:] != rate[:-1]).sum()),
        timestamp_wraps=int(wrap_steps.sum()),
    )


def _count_csv_rows(path: Path) -> int:
    df = pd.read_csv(path, usecols=[0], compression="infer")
    return int(len(df))


# ----------------------------------------------------------------- folder parsing


def _scan(src_dir: Path) -> list[_SrcFile]:
    if not src_dir.is_dir():
        raise IngestError(f"not a directory: {src_dir.name}")
    csi = sorted(src_dir.glob(CSI_GLOB))
    if not csi:
        raise IngestError(f"no {CSI_GLOB} files in {src_dir.name}")
    if not (src_dir / META_NAME).is_file():
        raise IngestError(f"{META_NAME} missing in {src_dir.name}")
    out = [
        _SrcFile(p, p.name, "csi", sha256_file(p), p.stat().st_size, _count_csv_rows(p))
        for p in csi
    ]
    meta = src_dir / META_NAME
    out.append(_SrcFile(meta, META_NAME, "meta", sha256_file(meta), meta.stat().st_size))
    mk = src_dir / MARKERS_NAME
    if mk.is_file():
        out.append(
            _SrcFile(mk, MARKERS_NAME, "markers", sha256_file(mk), mk.stat().st_size,
                     _count_csv_rows(mk))
        )  # fmt: skip
    return out


def _parse_meta(path: Path, user_id: str, session_id: str) -> SessionRecord:
    try:
        meta = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise IngestError(f"{META_NAME} is not valid JSON") from exc
    if not isinstance(meta, dict) or {"id", "user_id"} & meta.keys():
        raise IngestError(f"{META_NAME} must be an object without id/user_id")
    try:
        return SessionRecord(id=session_id, user_id=user_id, **meta)
    except ValueError as exc:
        raise IngestError(f"{META_NAME} invalid: {exc}") from exc


def _parse_markers(path: Path, session_id: str) -> list[MarkerRecord]:
    if not path.is_file():
        return []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return []
        if set(reader.fieldnames) != {"host_time_utc", "label"}:
            raise IngestError(f"{MARKERS_NAME} columns must be host_time_utc,label")
        try:
            return [
                MarkerRecord(session_id=session_id, host_time=r["host_time_utc"], label=r["label"])
                for r in reader
            ]
        except ValueError as exc:
            raise IngestError(f"{MARKERS_NAME} invalid: {exc}") from exc


# ----------------------------------------------------------------- copy


def _copy_into_store(files: list[_SrcFile], session_id: str) -> Path:
    """Stage copies in a temp dir, verify hashes, rename into raw/<session_id>/."""
    root = raw_root()
    root.mkdir(parents=True, exist_ok=True)
    final = root / session_id
    if final.exists():
        raise IngestError(f"raw folder for session {session_id} already exists")
    staging = root / f".staging-{session_id}"
    staging.mkdir()
    try:
        for f in files:
            dst = staging / f.name
            shutil.copyfile(f.src, dst)
            if sha256_file(dst) != f.sha256:
                raise IngestError(f"{f.name} changed while copying")
            os.chmod(dst, stat.S_IRUSR | stat.S_IRGRP)
        os.replace(staging, final)
    except BaseException:
        _remove_tree(staging)
        raise
    return final


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    for p in path.rglob("*"):
        if p.is_file():
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    shutil.rmtree(path, ignore_errors=True)


# ----------------------------------------------------------------- records


def _to_record(db: Session, s: CaptureSession) -> SessionRecord:
    files = db.scalars(
        scoped(select(RawFile), RawFile, s.user_id)
        .where(RawFile.session_id == s.id)
        .order_by(RawFile.path)
    ).all()
    return SessionRecord(
        id=s.id,
        user_id=s.user_id,
        start_utc=s.start_utc,
        end_utc=s.end_utc,
        condition=s.condition,
        distance_m=s.distance_m,
        posture=s.posture,
        paced_bpm=s.paced_bpm,
        reference_device=s.reference_device,
        room_notes=s.room_notes,
        phone_model=s.phone_model,
        source_kind=s.source_kind,
        files=[
            RawFileRecord(path=f.path, sha256=f.sha256, rows=f.rows, kind=f.kind) for f in files
        ],
        stats=CaptureStats(
            rows=s.rows,
            duration_s=s.duration_s,
            mean_rows_per_s=s.mean_rows_per_s,
            max_gap_s=s.max_gap_s,
            gaps_over_50ms=s.gaps_over_50ms,
            rate_changes=s.rate_changes,
            timestamp_wraps=s.timestamp_wraps,
        ),  # fmt: skip
        usable=s.usable,
    )


def _existing(db: Session, user_id: str, sess_hash: str) -> CaptureSession | None:
    return db.scalars(
        scoped(select(CaptureSession), CaptureSession, user_id).where(
            CaptureSession.raw_sha256 == sess_hash
        )
    ).one_or_none()


# ----------------------------------------------------------------- entry point


def ingest_session(db: Session, user_id: str, src_dir: Path) -> SessionRecord:
    """Ingest a capture folder for user_id. Idempotent by sha256."""
    src_dir = Path(src_dir)
    if db.get(User, user_id) is None:
        raise IngestError("unknown user")
    cfg = get_config()

    files = _scan(src_dir)
    csi = [f for f in files if f.kind == "csi"]
    sess_hash = session_hash([f.sha256 for f in csi])

    found = _existing(db, user_id, sess_hash)
    if found is not None:
        log.info("ingest: session %s already ingested, skipping", found.id)
        return _to_record(db, found)

    hashes = [f.sha256 for f in files]
    known = db.scalars(
        scoped(select(RawFile.sha256), RawFile, user_id).where(RawFile.sha256.in_(hashes))
    ).all()
    if known:
        raise IngestError(
            f"{len(known)} of {len(files)} files already belong to another session; "
            "overlapping or edited capture, not ingested"
        )

    session_id = new_id()
    rec = _parse_meta(src_dir / META_NAME, user_id, session_id)
    markers = _parse_markers(src_dir / MARKERS_NAME, session_id)
    stats = compute_capture_stats([f.src for f in csi], cfg)
    usable = stats.rows > 0 and stats.mean_rows_per_s >= cfg.capture.min_rows_per_s

    # Copy BEFORE the DB transaction; on DB failure the copy is removed.
    dest = _copy_into_store(files, session_id)
    rel = dest.relative_to(get_settings().data_dir).as_posix()
    try:
        row = CaptureSession(
            id=session_id,
            user_id=user_id,
            start_utc=rec.start_utc,
            end_utc=rec.end_utc,
            condition=rec.condition,
            distance_m=rec.distance_m,
            posture=rec.posture.value if rec.posture else None,
            paced_bpm=rec.paced_bpm,
            reference_device=rec.reference_device,
            room_notes=rec.room_notes,
            phone_model=rec.phone_model,
            source_kind=rec.source_kind.value,
            raw_path=rel,
            raw_sha256=sess_hash,
            usable=usable,
            **stats.model_dump(),
        )
        db.add(row)
        db.flush()  # parent first: FKs are enforced
        db.add_all(
            RawFile(
                user_id=user_id,
                session_id=session_id,
                path=f"{rel}/{f.name}",
                sha256=f.sha256,
                size_bytes=f.size,
                rows=f.rows,
                kind=f.kind,
            )  # fmt: skip
            for f in files
        )
        db.add_all(
            Marker(user_id=user_id, session_id=session_id, host_time=m.host_time, label=m.label)
            for m in markers
        )
        db.commit()
    except BaseException as exc:
        db.rollback()
        _remove_tree(dest)
        if isinstance(exc, IntegrityError):
            # Lost a race with a concurrent ingest of the same folder.
            found = _existing(db, user_id, sess_hash)
            if found is not None:
                return _to_record(db, found)
        raise

    log.info(
        "ingest: session %s, %d files, %d rows, usable=%s",
        session_id, len(files), stats.rows, usable,
    )  # fmt: skip
    return _to_record(db, row)

"""Encrypted backup and verified restore (plan §10: back up encrypted, test restoring).

Archive = header + encrypted chunks. Plaintext is a gzip tar with:
- manifest.json: format version, created_at, code version, alembic revision, per-table
  row counts, the DB snapshot's sha256, and every raw file (relative path, sha256, size);
- db/astro.db: an online snapshot via the sqlite3 backup API (consistent under WAL);
- data/<raw path>: the raw files themselves (unless include_raw=False).
Nothing else is ever added: never .env, never a key.

Crypto: key = HKDF-SHA256(FIELD_KEY, salt=random 16 bytes per archive,
info=b"astro:backup:v1"), AES-256-GCM over 1 MiB chunks, STREAM construction:
nonce = 7-byte random prefix || 4-byte chunk index || 1-byte last flag, and the header as
associated data, so reordered, dropped, truncated or extended archives fail to decrypt.

Restore verifies everything (decrypt, manifest, DB hash, raw hashes, overwrite rules)
before writing anything, writes raw files first and the DB last, then re-checks row
counts. Run it with the API stopped.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import stat
import struct
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.config import get_settings
from backend.db import sqlite_path
from backend.services.ingestion import sha256_file
from csi_core.config import ROOT

FORMAT_VERSION = 1
MAGIC = b"ASTROBK\x01"
HKDF_INFO = b"astro:backup:v1"
SALT_LEN = 16
PREFIX_LEN = 7
HEADER_LEN = len(MAGIC) + SALT_LEN + PREFIX_LEN
CHUNK = 1 << 20
_TAG = 16
MANIFEST = "manifest.json"
DB_MEMBER = "db/astro.db"
RAW_PREFIX = "data/"


class BackupError(RuntimeError):
    """Backup or restore cannot proceed. Messages never contain keys or file contents."""


class RestoreRefused(BackupError):
    """Restore would overwrite existing data and --force was not given."""


# ----------------------------------------------------------------- crypto


def _field_key() -> bytes:
    key = get_settings().field_key
    if not key:
        # No test fallback here: an archive under an ephemeral key could never be restored.
        raise BackupError("FIELD_KEY is not set; backups are encrypted with a key derived from it")
    return key.encode()


def _derive(field_key: bytes, salt: bytes) -> AESGCM:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=HKDF_INFO).derive(field_key)
    return AESGCM(key)


def _nonce(prefix: bytes, index: int, last: bool) -> bytes:
    if index >= 1 << 32:
        raise BackupError("archive too large")
    return prefix + struct.pack(">I", index) + (b"\x01" if last else b"\x00")


def encrypt_stream(src: BinaryIO, dst: BinaryIO, field_key: bytes) -> None:
    salt, prefix = os.urandom(SALT_LEN), os.urandom(PREFIX_LEN)
    header = MAGIC + salt + prefix
    aead = _derive(field_key, salt)
    dst.write(header)
    index = 0
    chunk = src.read(CHUNK)
    while True:
        nxt = src.read(CHUNK)
        last = not nxt
        ct = aead.encrypt(_nonce(prefix, index, last), chunk, header)
        dst.write(b"\x01" if last else b"\x00")
        dst.write(struct.pack(">I", len(ct)))
        dst.write(ct)
        if last:
            return
        chunk, index = nxt, index + 1


def _read_exact(f: BinaryIO, n: int) -> bytes:
    b = f.read(n)
    if len(b) != n:
        raise BackupError("archive is truncated or corrupt")
    return b


def decrypt_stream(src: BinaryIO, dst: BinaryIO, field_key: bytes) -> None:
    header = src.read(HEADER_LEN)
    if len(header) != HEADER_LEN or not header.startswith(MAGIC):
        raise BackupError("not an astro backup archive (or unsupported version)")
    salt = header[len(MAGIC) : len(MAGIC) + SALT_LEN]
    prefix = header[len(MAGIC) + SALT_LEN :]
    aead = _derive(field_key, salt)
    index = 0
    while True:
        flag = src.read(1)
        if not flag:
            raise BackupError("archive is truncated or corrupt")
        if flag not in (b"\x00", b"\x01"):
            raise BackupError("archive is truncated or corrupt")
        (n,) = struct.unpack(">I", _read_exact(src, 4))
        if not _TAG <= n <= CHUNK + _TAG:
            raise BackupError("archive is truncated or corrupt")
        ct = _read_exact(src, n)
        last = flag == b"\x01"
        try:
            dst.write(aead.decrypt(_nonce(prefix, index, last), ct, header))
        except InvalidTag:
            raise BackupError("cannot decrypt: wrong FIELD_KEY or corrupted archive") from None
        if last:
            if src.read(1):
                raise BackupError("archive has trailing data")
            return
        index += 1


# ----------------------------------------------------------------- helpers


def _db_path() -> Path:
    p = sqlite_path(get_settings().database_url)
    if p is None:
        raise BackupError("backup/restore needs a file-based SQLite DATABASE_URL")
    return p


@contextmanager
def _private_tmp() -> Iterator[Path]:
    """0700 scratch dir on the DATA_DIR volume (plaintext never lands in the repo or /tmp)."""
    base = get_settings().data_dir
    base.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix=".backup-", dir=base))
    try:
        yield d
    finally:
        _rmtree(d)


def _rmtree(path: Path) -> None:
    if not path.exists():
        return
    for p in path.rglob("*"):
        if p.is_file():
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    shutil.rmtree(path, ignore_errors=True)


def _snapshot(src: Path, dst: Path) -> None:
    with closing(sqlite3.connect(src)) as s, closing(sqlite3.connect(dst)) as d:
        s.backup(d)


def _table_counts(db: Path) -> dict[str, int]:
    with closing(sqlite3.connect(db)) as c:
        names = [
            r[0]
            for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]
        return {n: c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}


def _alembic_revision(db: Path) -> str | None:
    with closing(sqlite3.connect(db)) as c:
        try:
            row = c.execute("SELECT version_num FROM alembic_version").fetchone()
        except sqlite3.OperationalError:
            return None
    return row[0] if row else None


def _safe_rel(path: str) -> PurePosixPath:
    p = PurePosixPath(path)
    if p.is_absolute() or not p.parts or any(part in ("", ".", "..") for part in p.parts):
        raise BackupError("unsafe path in archive manifest")
    return p


def _code_version() -> str:
    from backend.services.runs import code_version

    return code_version()


def _assert_outside_repo(path: Path) -> None:
    if path.resolve().is_relative_to(ROOT.resolve()):
        raise BackupError("refusing to write a backup inside the repo (it is synced to Drive)")


# ----------------------------------------------------------------- backup


@dataclass(frozen=True)
class BackupSummary:
    out: str
    tables: int
    rows: int
    raw_files: int
    raw_included: bool
    bytes: int


def create_backup(out: Path, *, include_raw: bool = True) -> BackupSummary:
    out = Path(out)
    _assert_outside_repo(out)
    if out.exists():
        raise BackupError("output file already exists")
    field_key = _field_key()
    db = _db_path()
    if not db.exists():
        raise BackupError("database file does not exist")
    data_dir = get_settings().data_dir

    with _private_tmp() as tmp:
        snap = tmp / "astro.db"
        _snapshot(db, snap)
        counts = _table_counts(snap)
        with closing(sqlite3.connect(snap)) as c:
            raw_rows = c.execute(
                "SELECT path, sha256, size_bytes FROM raw_files ORDER BY path"
            ).fetchall()
        raw = []
        for path, sha, size in raw_rows:
            rel = _safe_rel(path)
            disk = data_dir.joinpath(*rel.parts)
            if not disk.is_file() or sha256_file(disk) != sha:
                raise BackupError(f"raw file missing or changed on disk: {rel}")
            raw.append({"path": str(rel), "sha256": sha, "size": size})
        manifest = {
            "format_version": FORMAT_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "code_version": _code_version(),
            "alembic_revision": _alembic_revision(snap),
            "db_sha256": sha256_file(snap),
            "tables": counts,
            "raw_included": include_raw,
            "raw": raw,
        }

        plain = tmp / "archive.tar.gz"
        with tarfile.open(plain, "w:gz", format=tarfile.PAX_FORMAT) as tar:
            body = json.dumps(manifest, indent=2, sort_keys=True).encode()
            info = tarfile.TarInfo(MANIFEST)
            info.size, info.mode = len(body), 0o600
            tar.addfile(info, io.BytesIO(body))
            tar.add(snap, arcname=DB_MEMBER, recursive=False)
            if include_raw:
                for r in raw:
                    rel = PurePosixPath(r["path"])
                    tar.add(data_dir.joinpath(*rel.parts), arcname=RAW_PREFIX + str(rel),
                            recursive=False)  # fmt: skip

        partial = out.with_name(out.name + ".partial")
        out.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as dst, plain.open("rb") as src:
                encrypt_stream(src, dst, field_key)
            os.replace(partial, out)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise

    return BackupSummary(
        out=str(out), tables=len(counts), rows=sum(counts.values()), raw_files=len(raw),
        raw_included=include_raw, bytes=out.stat().st_size,
    )  # fmt: skip


# ----------------------------------------------------------------- restore


@dataclass(frozen=True)
class RestoreSummary:
    tables: int
    rows: int
    raw_files: int
    raw_written: int
    alembic_revision: str | None


def _db_has_rows(db: Path) -> bool:
    if not db.exists() or db.stat().st_size == 0:
        return False
    counts = _table_counts(db)
    return any(n for t, n in counts.items() if t != "alembic_version")


def _extract(plain: Path, dest: Path) -> tuple[dict[str, Any], Path, dict[str, Path]]:
    """Read only the expected members, as regular files, into dest. Never extractall."""
    with tarfile.open(plain, "r:gz") as tar:
        members = {m.name: m for m in tar.getmembers()}
        if len(members) != len(tar.getmembers()):
            raise BackupError("archive has duplicate members")
        if MANIFEST not in members or DB_MEMBER not in members:
            raise BackupError("archive is missing its manifest or database")

        def read(name: str) -> tarfile.ExFileObject:
            m = members[name]
            if not m.isreg():
                raise BackupError("archive member is not a regular file")
            f = tar.extractfile(m)
            assert f is not None
            return f

        manifest = json.loads(read(MANIFEST).read())
        if manifest.get("format_version") != FORMAT_VERSION:
            raise BackupError("unsupported backup format version")
        raw = manifest.get("raw", [])
        expected = {MANIFEST, DB_MEMBER}
        if manifest.get("raw_included"):
            expected |= {RAW_PREFIX + str(_safe_rel(r["path"])) for r in raw}
        if set(members) != expected:
            raise BackupError("archive members do not match its manifest")

        db_out = dest / "astro.db"
        with db_out.open("wb") as fh:
            shutil.copyfileobj(read(DB_MEMBER), fh)
        raw_out: dict[str, Path] = {}
        if manifest.get("raw_included"):
            for i, r in enumerate(raw):
                p = dest / f"raw-{i}"
                with p.open("wb") as fh:
                    shutil.copyfileobj(read(RAW_PREFIX + str(_safe_rel(r["path"]))), fh)
                raw_out[r["path"]] = p
    return manifest, db_out, raw_out


def restore_backup(archive: Path, *, force: bool = False) -> RestoreSummary:
    archive = Path(archive)
    if not archive.is_file():
        raise BackupError("archive file not found")
    field_key = _field_key()
    target_db = _db_path()
    data_dir = get_settings().data_dir

    with _private_tmp() as tmp:
        plain = tmp / "archive.tar.gz"
        with archive.open("rb") as src, plain.open("wb") as dst:
            decrypt_stream(src, dst, field_key)
        manifest, snap, extracted = _extract(plain, tmp)

        # ---- verify everything before touching anything
        if sha256_file(snap) != manifest["db_sha256"]:
            raise BackupError("database snapshot hash does not match the manifest")
        if _table_counts(snap) != manifest["tables"]:
            raise BackupError("database snapshot row counts do not match the manifest")
        to_write: list[tuple[Path, Path]] = []
        for r in manifest["raw"]:
            rel = _safe_rel(r["path"])
            dest = data_dir.joinpath(*rel.parts)
            if not dest.resolve().is_relative_to(data_dir.resolve()):
                raise BackupError("raw path escapes DATA_DIR")
            if manifest["raw_included"]:
                src_file = extracted[r["path"]]
                if sha256_file(src_file) != r["sha256"]:
                    raise BackupError(f"raw file hash mismatch in archive: {rel}")
                if dest.exists():
                    if sha256_file(dest) == r["sha256"]:
                        continue
                    if not force:
                        raise RestoreRefused(f"a different raw file exists at {rel}; use --force")
                to_write.append((src_file, dest))
            elif not dest.is_file() or sha256_file(dest) != r["sha256"]:
                raise BackupError(f"raw file missing or different on disk: {rel}")
        if _db_has_rows(target_db) and not force:
            raise RestoreRefused("the target database is not empty; use --force to overwrite")

        # ---- write: raw files first (harmless if the DB step fails), DB last
        for src_file, dest in to_write:
            dest.parent.mkdir(parents=True, exist_ok=True)
            staging = dest.with_name(f".{dest.name}.restore")
            shutil.copyfile(src_file, staging)
            if dest.exists():
                os.chmod(dest, stat.S_IRUSR | stat.S_IWUSR)
            os.replace(staging, dest)
            os.chmod(dest, stat.S_IRUSR | stat.S_IRGRP)
        target_db.parent.mkdir(parents=True, exist_ok=True)
        _snapshot(snap, target_db)
        with closing(sqlite3.connect(target_db)) as c:
            c.execute("PRAGMA journal_mode=WAL")

    counts = _table_counts(target_db)
    if counts != manifest["tables"]:
        raise BackupError("restored row counts do not match the manifest")
    return RestoreSummary(
        tables=len(counts), rows=sum(counts.values()), raw_files=len(manifest["raw"]),
        raw_written=len(to_write), alembic_revision=manifest.get("alembic_revision"),
    )  # fmt: skip

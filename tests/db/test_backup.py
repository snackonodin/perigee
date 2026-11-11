from __future__ import annotations

import io
import json
import struct
import tarfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import select

from backend import db as db_mod
from backend import security
from backend.config import get_settings
from backend.db import sqlite_path
from backend.models import Profile, RawFile, SurveyResponseRow, User
from backend.services import backup as bk
from backend.services.ingestion import ingest_session, sha256_file
from csi_core.config import ROOT
from tools import cli

NAME = {"display": "Alice Backup-Marker"}
ANSWERS = {"phq2_1": 2, "phq2_2": 3}


def _set_key(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    monkeypatch.setenv("FIELD_KEY", key)
    get_settings.cache_clear()
    security.reset_key_cache()


@pytest.fixture
def field_key(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    key = Fernet.generate_key().decode()
    _set_key(monkeypatch, key)
    yield key
    get_settings.cache_clear()
    security.reset_key_cache()


@pytest.fixture
def populated(field_key: str, data_dir: Path, capture_dir: Path) -> Iterator[dict]:
    """Migrated DB (alembic) with a user, encrypted fields and an ingested session."""
    url = get_settings().database_url
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    engine = db_mod.init_db()
    with db_mod.SessionLocal() as s:
        u = User(email="alice@x", password_hash="x")
        s.add(u)
        s.flush()
        s.add(Profile(user_id=u.id, display_name=NAME))
        s.add(SurveyResponseRow(user_id=u.id, instrument_id="phq2", instrument_version="1.0",
                                administered_at=datetime(2026, 11, 1, tzinfo=UTC),
                                answers=ANSWERS))  # fmt: skip
        s.commit()
        rec = ingest_session(s, u.id, capture_dir)
        uid = u.id
    yield {"user_id": uid, "session_id": rec.id, "engine": engine}
    engine.dispose()
    db_mod.SessionLocal.configure(bind=None)


def _db_file() -> Path:
    p = sqlite_path(get_settings().database_url)
    assert p is not None
    return p


def _wipe(data_dir: Path, engine) -> None:
    engine.dispose()
    db = _db_file()
    for suffix in ("", "-wal", "-shm"):
        Path(str(db) + suffix).unlink(missing_ok=True)
    bk._rmtree(data_dir / "raw")


def _raw_hashes(data_dir: Path) -> dict[str, str]:
    root = data_dir / "raw"
    return {str(p.relative_to(data_dir)): sha256_file(p) for p in root.rglob("*") if p.is_file()}


def _counts() -> dict[str, int]:
    return bk._table_counts(_db_file())


def _out(tmp_path: Path) -> Path:
    return tmp_path / "backups" / "astro.astrobk"


def _decrypt_to_tar(archive: Path, key: str) -> bytes:
    buf = io.BytesIO()
    with archive.open("rb") as fh:
        bk.decrypt_stream(fh, buf, key.encode())
    return buf.getvalue()


# ----------------------------------------------------------------- round trip


def test_backup_wipe_restore_roundtrip(populated, data_dir, tmp_path, field_key) -> None:
    counts, hashes = _counts(), _raw_hashes(data_dir)
    assert counts["users"] == 1 and counts["raw_files"] == 4 and len(hashes) == 4

    summary = bk.create_backup(_out(tmp_path))
    assert summary.raw_files == 4 and summary.raw_included
    _wipe(data_dir, populated["engine"])
    assert not _db_file().exists() and not (data_dir / "raw").exists()

    res = bk.restore_backup(_out(tmp_path))
    assert res.raw_written == 4 and res.alembic_revision is not None
    assert _counts() == counts
    assert _raw_hashes(data_dir) == hashes
    assert all(not (p.stat().st_mode & 0o222) for p in (data_dir / "raw").rglob("*") if p.is_file())

    engine = db_mod.init_db()
    try:
        with db_mod.SessionLocal() as s:  # encrypted fields still decrypt with FIELD_KEY
            assert s.scalars(select(Profile)).one().display_name == NAME
            assert s.scalars(select(SurveyResponseRow)).one().answers == ANSWERS
            for f in s.scalars(select(RawFile)):
                assert sha256_file(data_dir / f.path) == f.sha256
    finally:
        engine.dispose()
    assert not list(data_dir.glob(".backup-*"))  # scratch dirs cleaned up


def test_no_raw_backup_verifies_disk_files(populated, data_dir, tmp_path) -> None:
    counts = _counts()
    assert not bk.create_backup(_out(tmp_path), include_raw=False).raw_included
    populated["engine"].dispose()
    _db_file().unlink()
    assert bk.restore_backup(_out(tmp_path)).raw_written == 0
    assert _counts() == counts

    victim = next((data_dir / "raw").rglob("csi_*"))
    bk._rmtree(victim.parent)
    _db_file().unlink()
    with pytest.raises(bk.BackupError, match="missing or different on disk"):
        bk.restore_backup(_out(tmp_path))
    assert not _db_file().exists()  # verified before writing anything


# ----------------------------------------------------------------- overwrite rules


def test_refuses_non_empty_db_without_force(populated, data_dir, tmp_path) -> None:
    bk.create_backup(_out(tmp_path))
    with db_mod.SessionLocal() as s:
        s.add(User(email="new@x", password_hash="x"))
        s.commit()
    before = _counts()
    with pytest.raises(bk.RestoreRefused, match="not empty"):
        bk.restore_backup(_out(tmp_path))
    assert _counts() == before
    populated["engine"].dispose()
    bk.restore_backup(_out(tmp_path), force=True)
    assert _counts()["users"] == before["users"] - 1


def test_refuses_different_raw_file_without_force(populated, data_dir, tmp_path) -> None:
    bk.create_backup(_out(tmp_path))
    _wipe(data_dir, populated["engine"])
    bk.restore_backup(_out(tmp_path))
    victim = next((data_dir / "raw").rglob("meta.json"))
    victim.chmod(0o600)
    victim.write_text("{}")
    _db_file().unlink()
    with pytest.raises(bk.RestoreRefused, match="different raw file"):
        bk.restore_backup(_out(tmp_path))
    assert not _db_file().exists()
    bk.restore_backup(_out(tmp_path), force=True)
    assert victim.read_text() != "{}"


# ----------------------------------------------------------------- crypto and safety


def test_archive_never_contains_key_or_env(populated, data_dir, tmp_path, field_key) -> None:
    out = _out(tmp_path)
    bk.create_backup(out)
    raw_bytes = out.read_bytes()
    assert field_key.encode() not in raw_bytes and b"Backup-Marker" not in raw_bytes
    plain = _decrypt_to_tar(out, field_key)
    for secret in (field_key, get_settings().secret_key):
        assert secret.encode() not in plain
    with tarfile.open(fileobj=io.BytesIO(plain), mode="r:gz") as tar:
        names = set(tar.getnames())
        manifest = json.loads(tar.extractfile("manifest.json").read())
    assert names == {"manifest.json", "db/astro.db"} | {
        "data/" + r["path"] for r in manifest["raw"]
    }
    assert not any(n.endswith(".env") or "key" in n.lower() for n in names)
    assert manifest["tables"]["raw_files"] == 4 and len(manifest["raw"]) == 4


def test_wrong_key_fails_and_touches_nothing(populated, data_dir, tmp_path, monkeypatch) -> None:
    bk.create_backup(_out(tmp_path))
    _wipe(data_dir, populated["engine"])
    _set_key(monkeypatch, Fernet.generate_key().decode())
    with pytest.raises(bk.BackupError, match="wrong FIELD_KEY or corrupted"):
        bk.restore_backup(_out(tmp_path))
    assert not _db_file().exists() and not (data_dir / "raw").exists()


@pytest.mark.parametrize("damage", ["flip", "truncate", "append", "drop_last", "header"])
def test_tampered_archive_fails(populated, tmp_path, damage) -> None:
    out = _out(tmp_path)
    bk.create_backup(out)
    b = bytearray(out.read_bytes())
    if damage == "flip":
        b[len(b) // 2] ^= 0x01
    elif damage == "truncate":
        b = b[: len(b) - 10]
    elif damage == "append":
        b += b"\x00" * 8
    elif damage == "header":
        b[0] ^= 0xFF
    else:  # cut the stream right before the final chunk's header
        b = b[: bk.HEADER_LEN]
    out.write_bytes(bytes(b))
    populated["engine"].dispose()
    _db_file().unlink()
    with pytest.raises(bk.BackupError):
        bk.restore_backup(out)
    assert not _db_file().exists()


def test_reordered_chunks_fail(monkeypatch, field_key) -> None:
    monkeypatch.setattr(bk, "CHUNK", 64)
    data = bytes(range(256)) * 2  # 8 chunks
    enc = io.BytesIO()
    bk.encrypt_stream(io.BytesIO(data), enc, field_key.encode())
    blob = enc.getvalue()
    head, rest = blob[: bk.HEADER_LEN], blob[bk.HEADER_LEN :]
    chunks, i = [], 0
    while i < len(rest):
        (n,) = struct.unpack(">I", rest[i + 1 : i + 5])
        chunks.append(rest[i : i + 5 + n])
        i += 5 + n
    assert len(chunks) == 8
    out = io.BytesIO()
    bk.decrypt_stream(io.BytesIO(blob), out, field_key.encode())
    assert out.getvalue() == data
    swapped = head + chunks[1] + chunks[0] + b"".join(chunks[2:])
    with pytest.raises(bk.BackupError):
        bk.decrypt_stream(io.BytesIO(swapped), io.BytesIO(), field_key.encode())
    dropped = head + b"".join(chunks[:3] + chunks[4:])
    with pytest.raises(bk.BackupError):
        bk.decrypt_stream(io.BytesIO(dropped), io.BytesIO(), field_key.encode())


def test_manifest_member_mismatch_rejected(field_key, data_dir, tmp_path) -> None:
    """A validly encrypted archive with an unexpected member (e.g. ../ path) is refused."""
    plain = io.BytesIO()
    with tarfile.open(fileobj=plain, mode="w:gz") as tar:
        for name, body in (("manifest.json", json.dumps({"format_version": 1, "raw": [],
                                                          "raw_included": False}).encode()),
                           ("db/astro.db", b""), ("../evil", b"x")):  # fmt: skip
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    out = tmp_path / "evil.astrobk"
    with out.open("wb") as fh:
        bk.encrypt_stream(io.BytesIO(plain.getvalue()), fh, field_key.encode())
    with pytest.raises(bk.BackupError, match="do not match"):
        bk.restore_backup(out)
    assert not (data_dir.parent / "evil").exists()


def test_backup_requires_real_field_key(data_dir, tmp_path, monkeypatch) -> None:
    _set_key(monkeypatch, "")
    with pytest.raises(bk.BackupError, match="FIELD_KEY is not set"):
        bk.create_backup(_out(tmp_path))


def test_output_rules(populated, tmp_path) -> None:
    with pytest.raises(bk.BackupError, match="inside the repo"):
        bk.create_backup(ROOT / "backup.astrobk")
    assert not (ROOT / "backup.astrobk").exists()
    out = _out(tmp_path)
    bk.create_backup(out)
    assert (out.stat().st_mode & 0o777) == 0o600
    with pytest.raises(bk.BackupError, match="already exists"):
        bk.create_backup(out)


# ----------------------------------------------------------------- CLI


def _run(capsys, *argv: str) -> tuple[int, dict]:
    code = cli.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_cli_backup_restore(populated, data_dir, tmp_path, capsys) -> None:
    counts = _counts()
    out = _out(tmp_path)
    code, res = _run(capsys, "backup", "--out", str(out))
    assert code == 0 and res["status"] == "ok" and res["raw_files"] == 4
    code, res = _run(capsys, "restore", str(out))
    assert code == 2 and res["status"] == "refused"
    _wipe(data_dir, populated["engine"])
    code, res = _run(capsys, "restore", str(out))
    assert code == 0 and res["rows"] == sum(counts.values())
    assert _counts() == counts
    code, res = _run(capsys, "restore", str(tmp_path / "missing.astrobk"), "--force")
    assert code == 1 and res == {"status": "failed", "error": "archive file not found"}

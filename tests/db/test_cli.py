from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from backend import db as db_mod
from backend.models import Base, CaptureSession, PipelineRun, RawFile, User
from tools import cli


@pytest.fixture
def schema(engine: Engine) -> Engine:
    Base.metadata.create_all(engine)
    return engine


def _user(db: Session, email: str, synthetic: bool = False) -> User:
    u = User(email=email, password_hash="x", is_synthetic=synthetic)
    db.add(u)
    db.commit()
    return u


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, object]:
    code = cli.main(list(argv))
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip() else None


def _count(db: Session, model: type) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model))


def test_ingest_twice_same_counts(schema, db, capture_dir, capsys) -> None:
    u = _user(db, "a@x")
    code, out = _run(capsys, "ingest", "--user", "a@x", str(capture_dir))
    assert code == 0 and out[0]["files"] == 4
    counts = (_count(db, CaptureSession), _count(db, RawFile))
    code, out2 = _run(capsys, "ingest", "--user", u.id, str(capture_dir))
    assert code == 0 and out2[0]["session_id"] == out[0]["session_id"]
    assert (_count(db, CaptureSession), _count(db, RawFile)) == counts == (1, 4)


def test_ingest_bad_dir_exit_1(schema, db, tmp_path, capsys) -> None:
    _user(db, "a@x")
    code, out = _run(capsys, "ingest", "--user", "a@x", str(tmp_path / "missing"))
    assert code == 1 and "error" in out[0]


def test_unknown_user_is_an_error(schema, capture_dir) -> None:
    with pytest.raises(SystemExit, match="no such user"):
        cli.main(["ingest", "--user", "nobody@x", str(capture_dir)])


def test_process_records_a_run(schema, db, capture_dir, capsys, monkeypatch) -> None:
    u_id = _user(db, "a@x").id
    _, out = _run(capsys, "ingest", "--user", "a@x", str(capture_dir))
    sid = out[0]["session_id"]
    seen = {}

    def fake(db_: Session, run: PipelineRun) -> str:
        seen.update(run.parameters)
        return "ok"

    monkeypatch.setitem(cli.runs._HANDLERS, "process_session", fake)
    monkeypatch.setattr(cli, "PIPELINE_MODULES", ())
    code, rec = _run(capsys, "process", sid)
    assert code == 0 and rec["status"] == "succeeded"
    assert seen["session_id"] == sid
    assert len(rec["input_hashes"]) == 4  # every raw file of the session
    db.expire_all()
    assert db.get(PipelineRun, rec["id"]).user_id == u_id  # run is owned


def test_process_failing_kind_exits_1(schema, db, capture_dir, capsys, monkeypatch) -> None:
    _user(db, "a@x")
    _, out = _run(capsys, "ingest", "--user", "a@x", str(capture_dir))

    def boom(db_: Session, run: PipelineRun) -> str:
        raise RuntimeError("nope")

    monkeypatch.setitem(cli.runs._HANDLERS, "process_session", boom)
    monkeypatch.setattr(cli, "PIPELINE_MODULES", ())
    code, rec = _run(capsys, "process", out[0]["session_id"])
    assert code == 1 and rec["status"] == "failed"


def test_reset_demo_only_deletes_synthetic(schema, db, capture_dir, data_dir, capsys) -> None:
    real = _user(db, "real@x")
    persona = _user(db, "persona@x", synthetic=True)
    real_id, persona_id = real.id, persona.id
    _, out = _run(capsys, "ingest", "--user", persona.id, str(capture_dir))
    raw = data_dir / "raw" / out[0]["session_id"]
    assert raw.is_dir()

    code, dry = _run(capsys, "reset-demo")
    assert code == 2 and dry["would_delete_synthetic_users"] == 1
    assert raw.is_dir()

    code, res = _run(capsys, "reset-demo", "--yes")
    assert code == 0 and res == {"deleted_synthetic_users": 1, "real_users_kept": True}
    db.expire_all()
    assert db.get(User, real_id) is not None and db.get(User, persona_id) is None
    assert _count(db, CaptureSession) == 0
    assert not raw.exists()  # read-only raw files removed too


def test_seed_personas_smoke(schema, capsys, monkeypatch) -> None:
    """seed-personas end to end on a tiny raw capture (full checks: tests/pipeline)."""
    from backend.services import personas

    monkeypatch.setattr(personas, "DEMO_RAW_H", 0.05)  # 3-min raw part keeps this fast
    code, out = _run(capsys, "seed-personas", "--anchor", "2026-11-18")
    assert code == 0 and [p["key"] for p in out["personas"]] == [
        "steady", "breath-drift", "mental-dip",
    ]  # fmt: skip
    assert all(p["nights_run"] == 14 for p in out["personas"])


def test_export_writes_private_file_and_never_overwrites(schema, db, tmp_path, capsys) -> None:
    u = _user(db, "a@x")
    dest = tmp_path / "export.json"
    code, out = _run(capsys, "export", "--user", "a@x", "--out", str(dest))
    assert code == 0 and out["user_id"] == u.id
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    assert json.loads(dest.read_text())
    with pytest.raises(FileExistsError):
        cli.main(["export", "--user", "a@x", "--out", str(dest)])


def test_db_url_override(data_dir: Path, capsys) -> None:
    other = data_dir / "other" / "x.db"
    Base.metadata.create_all(db_mod.get_engine(f"sqlite:///{other}"))
    code = cli.main(["--db-url", f"sqlite:///{other}", "reset-demo"])  # dry run: exit 2
    out = json.loads(capsys.readouterr().out)
    assert code == 2 and other.parent.is_dir() and out["would_delete_synthetic_users"] == 0

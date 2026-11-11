from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from backend.models import Base, PipelineRun, User
from backend.schemas.contracts import RunStatus
from backend.services import runs

H1, H2 = "a" * 64, "b" * 64


@pytest.fixture
def schema(engine: Engine) -> Engine:
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def fake_kinds(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    handlers = dict(runs._HANDLERS)

    def ok(db: Session, run: PipelineRun) -> str:
        db.add(User(email=f"made-by-{run.id}@x", password_hash="x"))
        return f"made 1 user with {run.parameters['n']}"

    def boom(db: Session, run: PipelineRun) -> str:
        db.add(User(email="should-roll-back@x", password_hash="x"))
        db.flush()
        raise RuntimeError("estimator exploded")

    handlers.update(ok=ok, boom=boom)
    monkeypatch.setattr(runs, "_HANDLERS", handlers)
    monkeypatch.setenv("ASTRO_CODE_VERSION", "deadbeef")
    runs.code_version.cache_clear()
    yield
    runs.code_version.cache_clear()


def test_create_run_records_params_hashes_and_sha(schema: Engine, db: Session, fake_kinds) -> None:
    rec = runs.create_run(db, "ok", {"n": 3}, [H2, H1, H2])
    assert rec.status is RunStatus.queued
    assert rec.code_version == "deadbeef"
    assert rec.input_hashes == [H1, H2]  # deduplicated, sorted
    row = db.get(PipelineRun, rec.id)
    assert row.parameters == {"n": 3} and row.started is None


def test_execute_success_transitions(schema: Engine, db: Session, fake_kinds) -> None:
    rec = runs.create_run(db, "ok", {"n": 3}, [H1])
    done = runs.execute(db, rec.id)
    assert done.status is RunStatus.succeeded
    assert done.started and done.finished and done.finished >= done.started
    assert [w for w in ("queued", "running", "succeeded") if w in done.log] == [
        "queued", "running", "succeeded",
    ]  # fmt: skip
    assert "made 1 user with 3" in done.log
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_execute_failure_rolls_back_and_marks_failed(
    schema: Engine, db: Session, fake_kinds
) -> None:
    rec = runs.create_run(db, "boom", {}, [])
    done = runs.execute(db, rec.id)
    assert done.status is RunStatus.failed
    assert "RuntimeError: estimator exploded" in done.log
    assert db.scalar(select(func.count()).select_from(User)) == 0
    db.expire_all()
    assert db.get(PipelineRun, rec.id).status == "failed"


def test_execute_only_queued(schema: Engine, db: Session, fake_kinds) -> None:
    rec = runs.create_run(db, "ok", {"n": 1}, [])
    runs.execute(db, rec.id)
    with pytest.raises(ValueError, match="only queued"):
        runs.execute(db, rec.id)
    with pytest.raises(LookupError):
        runs.execute(db, "missing")


def test_create_run_validates(schema: Engine, db: Session, fake_kinds) -> None:
    with pytest.raises(ValueError, match="unknown run kind"):
        runs.create_run(db, "nope", {}, [])
    with pytest.raises(ValueError):
        runs.create_run(db, "ok", {}, ["not-a-sha"])
    assert db.scalar(select(func.count()).select_from(PipelineRun)) == 0


def test_builtin_kinds_registered(schema: Engine, db: Session) -> None:
    assert {"process_session", "run_nightly"} <= set(runs.registered_kinds())
    done = runs.execute(db, runs.create_run(db, "process_session", {}, []).id)
    assert done.status is RunStatus.failed and "session_id" in done.log


def test_code_version_is_git_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASTRO_CODE_VERSION", raising=False)
    runs.code_version.cache_clear()
    v = runs.code_version()
    runs.code_version.cache_clear()
    assert v == "unknown" or len(v.removesuffix("-dirty")) == 40


def _owner(db: Session) -> str:
    u = User(email="owner@x", password_hash="x")
    db.add(u)
    db.commit()
    return u.id


@pytest.mark.parametrize("kind", ["ok", "boom"])
def test_user_id_set_and_kept_through_execute(
    schema: Engine, db: Session, fake_kinds, kind: str
) -> None:
    uid = _owner(db)
    rec = runs.create_run(db, kind, {"n": 1}, [], user_id=uid)
    assert db.get(PipelineRun, rec.id).user_id == uid
    runs.execute(db, rec.id)
    db.expire_all()
    row = db.get(PipelineRun, rec.id)
    assert row.user_id == uid and row.status in ("succeeded", "failed")


def test_user_id_falls_back_to_params_and_must_agree(
    schema: Engine, db: Session, fake_kinds
) -> None:
    uid = _owner(db)
    rec = runs.create_run(db, "ok", {"n": 1, "user_id": uid}, [])
    assert db.get(PipelineRun, rec.id).user_id == uid
    with pytest.raises(ValueError, match="disagree"):
        runs.create_run(db, "ok", {"n": 1, "user_id": uid}, [], user_id="someone-else")
    glob = runs.create_run(db, "ok", {"n": 1}, [])  # global run: no owner
    assert db.get(PipelineRun, glob.id).user_id is None


def test_user_id_must_reference_a_user(schema: Engine, db: Session, fake_kinds) -> None:
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        runs.create_run(db, "ok", {"n": 1}, [], user_id="00000000-0000-0000-0000-000000000000")
    db.rollback()
    assert db.scalar(select(func.count()).select_from(PipelineRun)) == 0


def test_bogus_params_user_id_leaves_owner_null(schema: Engine, db: Session, fake_kinds) -> None:
    rec = runs.create_run(db, "ok", {"n": 1, "user_id": "x"}, [])  # "x" is not a user
    assert db.get(PipelineRun, rec.id).user_id is None
    assert rec.parameters["user_id"] == "x"  # params kept as given

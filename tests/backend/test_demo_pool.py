"""Per-visitor demo copies: private, complete, capped, and never touching the template."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, update

from backend.config import get_settings
from backend.models import (
    CaptureSession,
    NightFeaturesRow,
    PipelineRun,
    Profile,
    User,
    WindowEstimateRow,
)
from backend.services import accounts as acc
from tests.api.conftest import api, data_dir, db, engine  # noqa: F401  (fixtures)

PW = "long enough password"
DEMO = "drift@ex.com"


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS", "1")
    monkeypatch.setenv("DEMO_MAX_USERS", "2")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def template(db, data_dir):  # noqa: F811
    """A small synthetic persona: a run, a session with a raw file, windows, a night, traits."""
    uid = acc.signup(db, DEMO, PW).user_id
    db.execute(update(User).where(User.id == uid).values(is_synthetic=True))
    run = PipelineRun(user_id=uid, kind="seed", code_version="t")
    db.add(run)
    db.flush()
    raw = data_dir / "raw" / "template.bin"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"template raw")
    t0 = datetime(2026, 11, 10, 23, tzinfo=UTC)
    sess = CaptureSession(
        user_id=uid, start_utc=t0, end_utc=t0 + timedelta(hours=1),
        raw_path="raw/template.bin", raw_sha256="0" * 64, run_id=run.id,
    )
    db.add(sess)
    db.flush()
    for i in range(3):
        db.add(WindowEstimateRow(
            user_id=uid, session_id=sess.id, run_id=run.id,
            t_start=t0 + timedelta(minutes=i), t_end=t0 + timedelta(minutes=i + 1),
        ))
    db.add(NightFeaturesRow(user_id=uid, date=date(2026, 11, 11), run_id=run.id))
    prof = db.scalar(select(Profile).where(Profile.user_id == uid))
    prof.settings = {"traits": {"E": 12.0}, "traits_source": "mini_ipip", "keep": 1}
    db.commit()
    return uid, sess.id, raw


def _visitor(api):  # noqa: F811
    res = api.post("/api/v1/auth/demo")
    assert res.status_code == 200, res.text
    tok = res.json()["access_token"]
    return res.json()["user_id"], {"Authorization": f"Bearer {tok}"}


def test_visitor_gets_a_complete_private_copy(api, db, template, demo_on) -> None:  # noqa: F811
    t_uid, t_sess, _ = template
    v_uid, _ = _visitor(api)
    assert v_uid != t_uid
    db.expire_all()
    sess = db.scalars(select(CaptureSession).where(CaptureSession.user_id == v_uid)).all()
    assert len(sess) == 1 and sess[0].id != t_sess and sess[0].raw_path == ""
    wins = db.scalars(select(WindowEstimateRow).where(WindowEstimateRow.user_id == v_uid)).all()
    assert len(wins) == 3 and {w.session_id for w in wins} == {sess[0].id}  # remapped FK
    runs = {r.id for r in db.scalars(select(PipelineRun).where(PipelineRun.user_id == v_uid))}
    assert {w.run_id for w in wins} <= runs and runs
    assert db.scalars(
        select(NightFeaturesRow).where(NightFeaturesRow.user_id == v_uid)
    ).one().date == date(2026, 11, 11)
    prof = db.scalar(select(Profile).where(Profile.user_id == v_uid))
    assert prof.settings == {"keep": 1}  # traits stripped: each visitor takes the quiz
    # the template is unchanged
    assert len(db.scalars(
        select(WindowEstimateRow).where(WindowEstimateRow.user_id == t_uid)
    ).all()) == 3


def test_two_visitors_are_isolated(api, db, template, demo_on) -> None:  # noqa: F811
    _, ha = _visitor(api)
    _, hb = _visitor(api)
    assert api.patch("/api/v1/me", json={"display_name": "Visitor A"}, headers=ha).status_code \
        == 200
    assert api.get("/api/v1/me", headers=hb).json().get("display_name") != "Visitor A"


def test_cap_returns_503_demo_full(api, db, template, demo_on) -> None:  # noqa: F811
    _visitor(api)
    _visitor(api)
    res = api.post("/api/v1/auth/demo")
    assert res.status_code == 503 and res.json()["error"] == "demo_full"


def test_deleting_a_visitor_frees_a_slot_and_keeps_template_files(
    api, db, template, demo_on  # noqa: F811
) -> None:
    _, raw = template[0], template[2]
    _, ha = _visitor(api)
    _visitor(api)
    assert api.delete("/api/v1/me", headers=ha).status_code == 204
    assert raw.read_bytes() == b"template raw"
    assert api.post("/api/v1/auth/demo").status_code == 200


def test_signup_cap(api, db, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setenv("SIGNUP_MAX_USERS", "1")
    get_settings.cache_clear()
    try:
        ok = api.post("/api/v1/auth/signup", json={"email": "a@example.test", "password": PW})
        assert ok.status_code in (200, 201), ok.text
        res = api.post("/api/v1/auth/signup", json={"email": "b@example.test", "password": PW})
        assert res.status_code == 403 and res.json()["error"] == "signup_closed"
    finally:
        get_settings.cache_clear()


def test_demo_stats_are_aggregate_only(api, db, template, demo_on) -> None:  # noqa: F811
    _, ha = _visitor(api)
    _visitor(api)
    assert api.delete("/api/v1/me", headers=ha).status_code == 204
    j = api.get("/api/v1/demo/stats").json()
    assert j == {"visitors_now": 1, "demo_sessions_started": 2, "cap": 2}

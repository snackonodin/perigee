"""Public no-login demo (Space Apps rule): off by default, synthetic persona only, undeletable."""

from __future__ import annotations

import pytest
from sqlalchemy import update

from backend.config import get_settings
from backend.models import User
from backend.services import accounts as acc
from tests.api.conftest import api, data_dir, db, engine  # noqa: F401  (fixtures)

PW = "long enough password"
DEMO = "persona-drift@example.invalid"


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_demo(db, synthetic: bool = True) -> str:  # noqa: F811
    uid = acc.signup(db, DEMO, PW).user_id
    db.execute(update(User).where(User.id == uid).values(is_synthetic=synthetic))
    db.commit()
    return uid


def test_demo_route_is_404_when_disabled(api, db) -> None:  # noqa: F811
    _seed_demo(db)
    res = api.post("/api/v1/auth/demo")
    assert res.status_code == 404


def test_demo_login_issues_tokens_for_a_private_synthetic_copy(api, db, demo_on) -> None:  # noqa: F811
    uid = _seed_demo(db)
    res = api.post("/api/v1/auth/demo")
    assert res.status_code == 200, res.text
    tok = res.json()["access_token"]
    me = api.get("/api/v1/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["id"] != uid and me["is_synthetic"] is True
    assert me["email"].startswith("demo-") and me["email"].endswith("@example.invalid")


def test_demo_never_reaches_a_real_account(api, db, demo_on) -> None:  # noqa: F811
    _seed_demo(db, synthetic=False)  # same e-mail but a real (non-synthetic) user
    assert api.post("/api/v1/auth/demo").status_code == 404


def test_demo_404_when_persona_not_seeded(api, db, demo_on) -> None:  # noqa: F811
    assert api.post("/api/v1/auth/demo").status_code == 404


def test_shared_demo_template_cannot_be_deleted(api, db, demo_on) -> None:  # noqa: F811
    _seed_demo(db)
    tok = acc.login(db, DEMO, PW).access_token  # the template itself, not a visitor copy
    res = api.delete("/api/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert res.status_code == 403 and res.json()["error"] == "demo_protected"
    assert api.post("/api/v1/auth/demo").status_code == 200  # still there


def test_a_visitor_may_delete_their_own_copy(api, db, demo_on) -> None:  # noqa: F811
    _seed_demo(db)
    tok = api.post("/api/v1/auth/demo").json()["access_token"]
    res = api.delete("/api/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert res.status_code == 204
    assert api.post("/api/v1/auth/demo").status_code == 200  # template untouched


def test_real_users_can_still_delete_themselves_with_demo_on(api, db, demo_on) -> None:  # noqa: F811
    _seed_demo(db)
    r = acc.signup(db, "real@example.invalid", PW)
    res = api.delete("/api/v1/me", headers={"Authorization": f"Bearer {r.access_token}"})
    assert res.status_code == 204

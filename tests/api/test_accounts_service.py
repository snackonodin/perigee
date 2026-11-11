from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text

from backend.models import AuditLog, Base, CaptureSession, RefreshToken, User
from backend.services import accounts as acc

PW = "long enough password"
T0 = datetime(2026, 11, 1, 22, 0, tzinfo=UTC)


def add_session(db, user_id: str, raw_path: str = "", sid: str | None = None) -> str:
    s = CaptureSession(
        id=sid or str(uuid.uuid4()), user_id=user_id, start_utc=T0,
        end_utc=T0 + timedelta(hours=1), raw_path=raw_path, raw_sha256=uuid.uuid4().hex * 2,
    )
    db.add(s)
    db.commit()
    return s.id


def _actions(db, user_id=None):
    stmt = select(AuditLog.action).order_by(AuditLog.ts)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    return list(db.scalars(stmt))


def test_signup_and_login(db) -> None:
    r = acc.signup(db, "  Alice@Example.COM ", PW)
    assert r.access_token and r.refresh_token and r.token_type == "bearer"
    user = db.get(User, r.user_id)
    assert user.email == "alice@example.com" and PW not in user.password_hash
    r2 = acc.login(db, "alice@example.com", PW)
    assert r2.user_id == r.user_id
    assert _actions(db, r.user_id) == ["auth.signup", "auth.login"]


@pytest.mark.parametrize("email,pw", [("bad", PW), ("a@b.co", "short"), ("a@b.co", "x" * 2000)])
def test_signup_rejects_bad_input(db, email, pw) -> None:
    with pytest.raises(acc.InvalidInput):
        acc.signup(db, email, pw)


def test_signup_duplicate_email(db) -> None:
    acc.signup(db, "a@b.co", PW)
    with pytest.raises(acc.EmailTaken):
        acc.signup(db, "A@B.CO", PW)


@pytest.mark.parametrize("email,pw", [("a@b.co", "wrong password"), ("nobody@b.co", PW),
                                      ("not-an-email", PW)])
def test_login_failures_look_the_same(db, email, pw) -> None:
    acc.signup(db, "a@b.co", PW)
    with pytest.raises(acc.InvalidCredentials) as e:
        acc.login(db, email, pw)
    assert str(e.value) == "invalid email or password"


def test_refresh_rotates_and_detects_reuse(db) -> None:
    r = acc.signup(db, "a@b.co", PW)
    r2 = acc.refresh(db, r.refresh_token)
    assert r2.refresh_token != r.refresh_token
    r3 = acc.refresh(db, r2.refresh_token)
    # replaying an old token revokes the whole family, including the newest one
    with pytest.raises(acc.InvalidRefreshToken):
        acc.refresh(db, r.refresh_token)
    with pytest.raises(acc.InvalidRefreshToken):
        acc.refresh(db, r3.refresh_token)
    assert "auth.refresh_reuse" in _actions(db, r.user_id)


def test_refresh_rejects_unknown_and_expired(db) -> None:
    r = acc.signup(db, "a@b.co", PW)
    with pytest.raises(acc.InvalidRefreshToken):
        acc.refresh(db, "not-a-token")
    db.query(RefreshToken).update({"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
    db.commit()
    with pytest.raises(acc.InvalidRefreshToken):
        acc.refresh(db, r.refresh_token)


def test_logout_revokes(db) -> None:
    r = acc.signup(db, "a@b.co", PW)
    acc.logout(db, r.refresh_token)
    acc.logout(db, r.refresh_token)  # idempotent
    acc.logout(db, "unknown")
    with pytest.raises(acc.InvalidRefreshToken):
        acc.refresh(db, r.refresh_token)


def test_logout_scoped_to_user(db) -> None:
    a = acc.signup(db, "a@b.co", PW)
    b = acc.signup(db, "b@b.co", PW)
    acc.logout(db, a.refresh_token, user_id=b.user_id)  # B cannot revoke A's token
    assert acc.refresh(db, a.refresh_token).user_id == a.user_id


def test_profile_update_and_encryption(db) -> None:
    r = acc.signup(db, "a@b.co", PW)
    me = acc.update_profile(db, r.user_id, {"display_name": "Ada", "timezone": "Asia/Kolkata"})
    assert me["display_name"] == "Ada" and me["timezone"] == "Asia/Kolkata"
    raw = db.connection().exec_driver_sql("SELECT display_name_enc FROM profiles").scalar_one()
    assert b"Ada" not in raw
    with pytest.raises(acc.InvalidInput):
        acc.update_profile(db, r.user_id, {"timezone": "Mars/Olympus"})
    with pytest.raises(acc.InvalidInput):
        acc.update_profile(db, r.user_id, {"email": "x@y.zz"})
    with pytest.raises(acc.InvalidInput):
        acc.update_profile(db, r.user_id, {"display_name": "x" * 129})


def test_consents_default_set_and_audit(db) -> None:
    r = acc.signup(db, "a@b.co", PW)
    c = acc.get_consents(db, r.user_id)
    assert set(c) == set(acc.CONSENT_SCOPES) and not any(v["granted"] for v in c.values())
    c = acc.set_consents(db, r.user_id, {"checkins": True, "raw_csi": False}, "v1")
    assert c["checkins"]["granted"] and c["checkins"]["policy_version"] == "v1"
    acc.set_consents(db, r.user_id, {"checkins": True}, "v1")  # no change: no new audit row
    assert _actions(db, r.user_id).count("consent.change") == 1
    with pytest.raises(acc.InvalidInput):
        acc.set_consents(db, r.user_id, {"telepathy": True}, "v1")


def test_export_has_all_rows_no_secrets(db) -> None:
    r = acc.signup(db, "a@b.co", PW)
    acc.update_profile(db, r.user_id, {"display_name": "Ada"})
    acc.set_consents(db, r.user_id, {"checkins": True}, "v1")
    other = acc.signup(db, "b@b.co", PW)
    out = acc.export_user(db, r.user_id)
    assert out["user"]["email"] == "a@b.co" and "password_hash" not in out["user"]
    t = out["tables"]
    assert t["profiles"][0]["display_name"] == "Ada"
    assert t["consents"][0]["scope"] == "checkins"
    assert t["refresh_tokens"] and all("token_sha256" not in x for x in t["refresh_tokens"])
    assert "account.export" in [x["action"] for x in t["audit_log"]]
    blob = repr(out)
    assert other.user_id not in blob and "b@b.co" not in blob
    assert r.refresh_token not in blob


def test_delete_user_removes_rows_files_tokens(db, data_dir) -> None:
    a = acc.signup(db, "a@b.co", PW)
    b = acc.signup(db, "b@b.co", PW)
    acc.update_profile(db, a.user_id, {"display_name": "Ada"})
    acc.set_consents(db, a.user_id, {"raw_csi": True}, "v1")
    dirs = {}
    for uid in (a.user_id, b.user_id):
        sid = add_session(db, uid)
        d = data_dir / "raw" / sid
        d.mkdir(parents=True)
        (d / "csi_00.csv.gz").write_bytes(b"x")
        dirs[uid] = d

    acc.delete_user(db, a.user_id)  # data_dir from settings (.env / DATA_DIR)

    for t in Base.metadata.sorted_tables:
        if "user_id" in t.c:
            n = db.scalar(select(func.count()).select_from(t).where(t.c.user_id == a.user_id))
            assert n == 0, t.name
    assert db.get(User, a.user_id) is None
    assert not dirs[a.user_id].exists()
    assert dirs[b.user_id].exists() and db.get(User, b.user_id) is not None
    with pytest.raises(acc.InvalidRefreshToken):
        acc.refresh(db, a.refresh_token)
    with pytest.raises(acc.InvalidCredentials):
        acc.login(db, "a@b.co", PW)
    # audit history survives anonymised, plus one anonymous delete row
    anon = list(db.scalars(select(AuditLog.action).where(AuditLog.user_id.is_(None))))
    assert anon.count("account.delete") == 1 and "auth.signup" in anon
    # B is untouched
    assert acc.refresh(db, b.refresh_token).user_id == b.user_id


def test_delete_removes_raw_path_inside_data_dir(db, data_dir) -> None:
    a = acc.signup(db, "a@b.co", PW)
    f = data_dir / "raw" / "2026-11-10" / "csi_00.csv.gz"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"x")
    add_session(db, a.user_id, raw_path="raw/2026-11-10")
    acc.delete_user(db, a.user_id)
    assert not f.parent.exists()


def test_delete_with_explicit_data_dir(db, tmp_path) -> None:
    a = acc.signup(db, "a@b.co", PW)
    sid = add_session(db, a.user_id)
    (tmp_path / "elsewhere" / "raw" / sid).mkdir(parents=True)
    acc.delete_user(db, a.user_id, tmp_path / "elsewhere")
    assert not (tmp_path / "elsewhere" / "raw" / sid).exists()


@pytest.mark.parametrize("raw_path", ["../outside", "raw", "/"])
def test_delete_refuses_raw_path_escape(db, data_dir, raw_path) -> None:
    a = acc.signup(db, "a@b.co", PW)
    victim = data_dir / "outside" / "keep.txt"
    victim.parent.mkdir()
    victim.write_text("x")
    add_session(db, a.user_id, raw_path=raw_path)
    with pytest.raises(ValueError):
        acc.delete_user(db, a.user_id)
    assert db.get(User, a.user_id) is not None  # rolled back, retryable
    assert victim.exists()


def test_delete_refuses_non_uuid_session_id(db, data_dir) -> None:
    # The model validator already rejects this; the service must not trust that alone.
    a = acc.signup(db, "a@b.co", PW)
    sid = add_session(db, a.user_id)
    db.execute(text("UPDATE sessions SET id = '../../etc' WHERE id = :s"), {"s": sid})
    db.commit()
    with pytest.raises(ValueError):
        acc.delete_user(db, a.user_id)
    assert db.get(User, a.user_id) is not None

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select, text

from backend import security
from backend.config import get_settings


def test_password_hash_roundtrip() -> None:
    h = security.hash_password("correct horse battery")
    assert h.startswith("$argon2id$")
    assert "correct horse" not in h
    assert security.verify_password(h, "correct horse battery")
    assert not security.verify_password(h, "wrong password!!")
    assert not security.verify_password("not-a-hash", "whatever")


def test_access_token_roundtrip() -> None:
    tok = security.make_access_token("user-123")
    assert security.decode_access_token(tok) == "user-123"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t + "x",
        lambda t: "garbage",
        lambda t: jwt.encode(
            {
                "sub": "u",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
                "typ": "access",
            },
            "another-secret-key-that-is-long-enough-for-hs256",
            algorithm="HS256",
        ),
        lambda t: jwt.encode(
            {
                "sub": "u",
                "iat": datetime.now(UTC) - timedelta(hours=2),
                "exp": datetime.now(UTC) - timedelta(hours=1),
                "typ": "access",
            },
            get_settings().secret_key,
            algorithm="HS256",
        ),
        lambda t: jwt.encode(
            {
                "sub": "u",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
                "typ": "refresh",
            },
            get_settings().secret_key,
            algorithm="HS256",
        ),
        lambda t: jwt.encode({"sub": "u", "typ": "access"}, get_settings().secret_key, "HS256"),
    ],
    ids=["tampered", "garbage", "wrong-key", "expired", "wrong-type", "no-exp"],
)
def test_bad_access_tokens_rejected(mutate) -> None:
    with pytest.raises(security.TokenError):
        security.decode_access_token(mutate(security.make_access_token("u")))


def test_refresh_token_stored_as_sha256() -> None:
    plain, digest = security.new_refresh_token()
    assert len(plain) >= 40
    assert len(digest) == 64 and plain not in digest
    assert security.hash_refresh_token(plain) == digest
    assert security.new_refresh_token()[0] != plain


def test_encrypt_roundtrip_and_tamper() -> None:
    ct = security.encrypt(b"secret dose 5mg")
    assert b"5mg" not in ct
    assert security.decrypt(ct) == b"secret dose 5mg"
    with pytest.raises(ValueError):
        security.decrypt(ct[:-4] + b"AAAA")


def test_field_key_required_outside_tests(monkeypatch) -> None:
    monkeypatch.setattr(security, "_under_pytest", lambda: False)
    monkeypatch.setattr(get_settings(), "field_key", "")
    security.reset_key_cache()
    try:
        with pytest.raises(security.FieldKeyMissing):
            security.encrypt(b"x")
    finally:
        security.reset_key_cache()


def test_configured_field_key_is_used(monkeypatch) -> None:
    key = Fernet.generate_key()
    monkeypatch.setattr(get_settings(), "field_key", key.decode())
    security.reset_key_cache()
    try:
        assert Fernet(key).decrypt(security.encrypt(b"hi")) == b"hi"
    finally:
        security.reset_key_cache()


def test_encrypted_json_column() -> None:
    md = MetaData()
    t = Table(
        "t", md, Column("id", Integer, primary_key=True), Column("v", security.EncryptedJSON())
    )
    eng = create_engine("sqlite://")
    md.create_all(eng)
    payload = {"q1": 3, "note": "felt dizzy"}
    with eng.begin() as c:
        c.execute(t.insert(), [{"id": 1, "v": payload}, {"id": 2, "v": None}])
    with eng.connect() as c:
        raw = c.execute(text("SELECT v FROM t WHERE id = 1")).scalar_one()
        assert b"dizzy" not in raw
        assert c.execute(select(t.c.v).where(t.c.id == 1)).scalar_one() == payload
        assert c.execute(select(t.c.v).where(t.c.id == 2)).scalar_one() is None

from __future__ import annotations

import logging

import pytest

PW = "long enough password"


def _signup(api, email="a@b.co", pw=PW) -> dict:
    res = api.post("/api/v1/auth/signup", json={"email": email, "password": pw})
    assert res.status_code == 201, res.text
    return res.json()


def _h(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _is_error(res, status: int, code: str) -> None:
    assert res.status_code == status, res.text
    body = res.json()
    assert body["error"] == code and isinstance(body["message"], str)
    assert set(body) <= {"error", "message", "fields"}


def test_signup_login_refresh_logout(api) -> None:
    t = _signup(api)
    assert t["token_type"] == "bearer" and t["expires_in"] > 0
    _is_error(
        api.post("/api/v1/auth/signup", json={"email": "A@b.co", "password": PW}),
        409,
        "email_taken",
    )
    t2 = api.post("/api/v1/auth/login", json={"email": "a@b.co", "password": PW}).json()
    assert t2["user_id"] == t["user_id"]
    r = api.post("/api/v1/auth/refresh", json={"refresh_token": t2["refresh_token"]})
    assert r.status_code == 200 and r.json()["refresh_token"] != t2["refresh_token"]
    t3 = r.json()
    assert (
        api.post("/api/v1/auth/logout", json={"refresh_token": t3["refresh_token"]}).status_code
        == 204
    )
    _is_error(
        api.post("/api/v1/auth/refresh", json={"refresh_token": t3["refresh_token"]}),
        401,
        "unauthorized",
    )


@pytest.mark.parametrize(
    "body,status,code",
    [
        ({"email": "a@b.co", "password": "short"}, 422, "validation_error"),
        ({"email": "nope", "password": PW}, 422, "invalid_input"),
        ({"email": "a@b.co"}, 422, "validation_error"),
        ({"email": "a@b.co", "password": PW, "admin": True}, 422, "validation_error"),
    ],
)
def test_signup_bad_input(api, body, status, code) -> None:
    res = api.post("/api/v1/auth/signup", json=body)
    _is_error(res, status, code)
    assert "short" not in res.text  # submitted values never echoed


def test_login_wrong_password_and_unknown_email_identical(api) -> None:
    _signup(api)
    a = api.post("/api/v1/auth/login", json={"email": "a@b.co", "password": "wrong password!"})
    b = api.post("/api/v1/auth/login", json={"email": "x@b.co", "password": PW})
    _is_error(a, 401, "unauthorized")
    assert a.json() == b.json() and a.status_code == b.status_code


def test_me_get_patch(api) -> None:
    t = _signup(api)
    me = api.get("/api/v1/me", headers=_h(t)).json()
    assert me["email"] == "a@b.co" and me["timezone"] == "UTC" and me["display_name"] is None
    res = api.patch("/api/v1/me", headers=_h(t), json={"display_name": "Ada"})
    assert res.json()["display_name"] == "Ada" and res.json()["timezone"] == "UTC"
    res = api.patch("/api/v1/me", headers=_h(t), json={"timezone": "Asia/Kolkata"})
    assert res.json()["display_name"] == "Ada" and res.json()["timezone"] == "Asia/Kolkata"
    _is_error(
        api.patch("/api/v1/me", headers=_h(t), json={"timezone": "Mars/Base"}), 422, "invalid_input"
    )
    _is_error(
        api.patch("/api/v1/me", headers=_h(t), json={"email": "x@y.zz"}), 422, "validation_error"
    )


def test_consents(api) -> None:
    t = _signup(api)
    c = api.get("/api/v1/me/consents", headers=_h(t)).json()
    assert set(c) == {"checkins", "survey_answers", "raw_csi", "share_summaries"}
    assert not any(v["granted"] for v in c.values())
    res = api.put(
        "/api/v1/me/consents",
        headers=_h(t),
        json={"scopes": {"checkins": True, "raw_csi": True}, "policy_version": "v1"},
    )
    assert res.status_code == 200
    assert res.json()["checkins"]["granted"] and not res.json()["share_summaries"]["granted"]
    _is_error(
        api.put(
            "/api/v1/me/consents",
            headers=_h(t),
            json={"scopes": {"telepathy": True}, "policy_version": "v1"},
        ),
        422,
        "validation_error",
    )
    _is_error(
        api.put("/api/v1/me/consents", headers=_h(t), json={"scopes": {}}), 422, "validation_error"
    )


def test_export_and_delete(api) -> None:
    t = _signup(api)
    api.patch("/api/v1/me", headers=_h(t), json={"display_name": "Ada"})
    ex = api.post("/api/v1/me/export", headers=_h(t))
    assert ex.status_code == 200
    body = ex.json()
    assert body["user"]["id"] == t["user_id"] and body["tables"]["profiles"][0]["display_name"]
    assert "password_hash" not in ex.text and "token_sha256" not in ex.text
    assert api.delete("/api/v1/me", headers=_h(t)).status_code == 204
    _is_error(api.get("/api/v1/me", headers=_h(t)), 401, "unauthorized")
    _is_error(
        api.post("/api/v1/auth/refresh", json={"refresh_token": t["refresh_token"]}),
        401,
        "unauthorized",
    )
    _is_error(
        api.post("/api/v1/auth/login", json={"email": "a@b.co", "password": PW}),
        401,
        "unauthorized",
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/me"),
        ("patch", "/api/v1/me"),
        ("delete", "/api/v1/me"),
        ("get", "/api/v1/me/consents"),
        ("put", "/api/v1/me/consents"),
        ("post", "/api/v1/me/export"),
    ],
)
def test_me_routes_require_auth(api, method, path) -> None:
    _is_error(api.request(method, path, json={}), 401, "unauthorized")


def test_no_secrets_in_logs_full_flow(api, caplog) -> None:
    """Raw records (before any redaction filter): our code must not emit secrets at all."""
    caplog.set_level(logging.DEBUG)
    t = _signup(api, pw="hunter2-correct-horse")
    api.post("/api/v1/auth/login", json={"email": "a@b.co", "password": "wrong-password-x"})
    t2 = api.post("/api/v1/auth/refresh", json={"refresh_token": t["refresh_token"]}).json()
    api.patch("/api/v1/me", headers=_h(t2), json={"display_name": "Zelda Quuxington"})
    api.put(
        "/api/v1/me/consents",
        headers=_h(t2),
        json={"scopes": {"checkins": True}, "policy_version": "v1"},
    )
    api.post("/api/v1/me/export", headers=_h(t2))
    api.delete("/api/v1/me", headers=_h(t2))
    text = caplog.text + "".join(str(r.__dict__) for r in caplog.records)
    for secret in (
        "hunter2-correct-horse",
        "wrong-password-x",
        t["access_token"],
        t["refresh_token"],
        t2["access_token"],
        t2["refresh_token"],
        "Zelda",
    ):
        assert secret not in text
    assert caplog.records  # the flow did log something

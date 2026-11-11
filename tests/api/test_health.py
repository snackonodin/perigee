from fastapi.testclient import TestClient

from backend.main import create_app


def test_health_and_version() -> None:
    c = TestClient(create_app(with_lifespan=False))
    assert c.get("/api/v1/health").json() == {"status": "ok"}
    assert c.get("/api/v1/version").json()["api"] == "v1"


def test_startup_inits_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    from backend.config import get_settings

    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as c:
            assert c.get("/api/v1/health").status_code == 200
        assert (tmp_path / "t.db").exists()
    finally:
        get_settings.cache_clear()


def test_unknown_route_uses_error_model() -> None:
    r = TestClient(create_app(with_lifespan=False)).get("/api/v1/nope")
    assert r.status_code == 404
    assert "error" in r.json()

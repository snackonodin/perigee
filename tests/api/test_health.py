import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


def test_health_and_version() -> None:
    c = TestClient(create_app(with_lifespan=False))
    assert c.get("/api/v1/health").json() == {"status": "ok"}
    assert c.get("/api/v1/version").json()["api"] == "v1"


@pytest.fixture
def fresh_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    from backend.config import get_settings

    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_startup_refuses_missing_schema(fresh_env) -> None:
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        with TestClient(create_app()):
            pass


def test_startup_seeds_catalog_and_runs_worker(fresh_env) -> None:
    from backend.db import get_engine
    from backend.models import Base

    Base.metadata.create_all(get_engine(f"sqlite:///{fresh_env}/t.db"))
    with TestClient(create_app()) as c:
        assert c.get("/api/v1/health").status_code == 200
        r = c.post("/api/v1/auth/signup", json={"email": "a@example.org", "password": "x" * 12})
        assert r.status_code in (200, 201)
        tok = c.post(
            "/api/v1/auth/login", json={"email": "a@example.org", "password": "x" * 12}
        ).json()["access_token"]
        ids = {i["id"] for i in c.get(
            "/api/v1/instruments", headers={"Authorization": f"Bearer {tok}"}
        ).json()}
        assert {"phq9", "who5", "daily_am"} <= ids


def test_unknown_route_uses_error_model() -> None:
    r = TestClient(create_app(with_lifespan=False)).get("/api/v1/nope")
    assert r.status_code == 404
    assert "error" in r.json()

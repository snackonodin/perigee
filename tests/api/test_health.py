from fastapi.testclient import TestClient

from backend.main import app


def test_health_and_version() -> None:
    c = TestClient(app)
    assert c.get("/api/v1/health").json() == {"status": "ok"}
    assert c.get("/api/v1/version").json()["api"] == "v1"

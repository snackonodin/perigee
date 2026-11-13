"""Deep links into the React app (refresh on /body, /monitor) must open the app, not 404."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.main import spa_files


def _client(tmp_path) -> TestClient:
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    app = FastAPI()

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.mount("/", spa_files(tmp_path), name="frontend")
    return TestClient(app)


def test_page_routes_fall_back_to_index(tmp_path) -> None:
    c = _client(tmp_path)
    for path in ("/", "/body", "/monitor", "/settings", "/night/2026-11-10"):
        res = c.get(path)
        assert res.status_code == 200 and "id=root" in res.text, path


def test_assets_and_api_are_not_masked(tmp_path) -> None:
    c = _client(tmp_path)
    assert c.get("/assets/app.js").status_code == 200
    assert c.get("/assets/missing.js").status_code == 404
    assert c.get("/api/v1/health").json() == {"status": "ok"}
    assert c.get("/api/v1/nope").status_code == 404
    assert "id=root" not in c.get("/api/v1/nope").text

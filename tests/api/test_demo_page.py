"""OPS-14 smoke tests for the offline demo page (backend/static/demo)."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from csi_core.config import ROOT

DEMO = ROOT / "backend" / "static" / "demo"
APP_JS = (DEMO / "app.js").read_text(encoding="utf-8")
SVG_NS = "http://www.w3.org/2000/svg"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(with_lifespan=False))


def test_demo_served(client) -> None:
    res = client.get("/demo/")
    assert res.status_code == 200 and "text/html" in res.headers["content-type"]
    assert 'src="app.js"' in res.text and 'href="app.css"' in res.text
    for asset in ("app.js", "app.css", "personas.json"):
        assert client.get(f"/demo/{asset}").status_code == 200, asset


def test_every_api_path_in_app_js_exists(client) -> None:
    used = set(re.findall(r"""["'`](/api/v1/[^"'`?]*)["'`]""", APP_JS))
    assert {"/api/v1/today", "/api/v1/auth/login", "/api/v1/responses"} <= used
    spec = set(client.get("/openapi.json").json()["paths"])
    missing = sorted(used - spec)
    assert not missing, f"app.js calls paths the API does not serve: {missing}"


def test_offline_no_external_resources() -> None:
    for f in DEMO.iterdir():
        text = f.read_text(encoding="utf-8").replace(SVG_NS, "")
        assert not re.search(r"https?://|(?<![:\w])//[a-z0-9.-]+\.[a-z]{2,}", text, re.I), f.name
    html = (DEMO / "index.html").read_text(encoding="utf-8")
    assert "<script>" not in html  # scripts only from same-origin files


def test_no_html_injection_apis() -> None:
    for api in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert api not in APP_JS, api


def test_safety_fallback_matches_seed() -> None:
    seed = json.loads((ROOT / "seeds" / "safety_resources.json").read_text(encoding="utf-8"))
    for line in seed["resources"]:
        assert json.dumps(line) in APP_JS, line
    assert json.dumps(seed["reasons"]["safety_item"]) in APP_JS


def test_safety_shown_before_score() -> None:
    """The local pre-check runs before the request; the server result before rendering."""
    body = APP_JS[APP_JS.index("async function submitCheckin") :]
    body = body[: body.index("\nfunction ")]
    assert body.index("showSafety(SAFETY_FALLBACK)") < body.index("PATHS.responses")
    assert body.index("out.safety.show") < body.index("renderCheckinResult(out)")
    assert "e.body.safety" in body  # a 500 from /responses still shows its safety result


def test_personas_file_has_no_passwords() -> None:
    data = json.loads((DEMO / "personas.json").read_text(encoding="utf-8"))
    for p in data["personas"]:
        assert set(p) <= {"email", "label", "description"}, p

"""Black-box checks for the currently documented public API contract.

The test migrates an isolated database, starts the real ASGI app, and records
contract mismatches before failing. Only synthetic account/survey values are
sent; no real user data belongs in the mismatch ledger.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
BUGS = ROOT / "coord" / "BUGS-api.md"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ContractClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def request(self, method: str, path: str, body=None, token: str | None = None, retries: int = 2):
        """One request. A bounded retry covers a transient socket timeout when the full
        suite loads the machine; it does not relax the 5 s per-request timeout."""
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        for attempt in range(retries + 1):
            try:
                with urlopen(request, timeout=5) as response:
                    raw = response.read()
                    return response.status, response.headers, self._decode(raw, response.headers)
            except HTTPError as error:
                raw = error.read()
                return error.code, error.headers, self._decode(raw, error.headers)
            except (TimeoutError, ConnectionError):
                if attempt == retries:
                    raise
                time.sleep(0.2 * (attempt + 1))
            except URLError as error:
                # urlopen wraps a socket timeout in URLError(reason=TimeoutError).
                if isinstance(error.reason, (TimeoutError, ConnectionError)) and attempt < retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise

    @staticmethod
    def _decode(raw: bytes, headers):
        if not raw:
            return None
        if "json" in headers.get("Content-Type", "").lower():
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        return raw.decode("utf-8", errors="replace")


def _record_mismatch(request: str, expected: str, actual: str) -> None:
    BUGS.parent.mkdir(parents=True, exist_ok=True)
    if not BUGS.exists():
        BUGS.write_text("# API contract mismatches\n\n", encoding="utf-8")
    with BUGS.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n## Mismatch\n- Request: {request}\n- Expected: {expected}\n- Actual: {actual}\n"
        )


def _check(request: str, expected: str, actual: str, ok: bool) -> None:
    if not ok:
        _record_mismatch(request, expected, actual)
    assert ok, f"{request}: expected {expected}; actual {actual}"


def _spawn_api(env: dict[str, str], tmp_path: Path) -> tuple[subprocess.Popen, ContractClient, Path]:
    """Start uvicorn on a fresh port and wait for /api/v1/health with a bounded retry loop.

    A port is probed once and can be taken between probe and bind, so a failed start is
    retried on a new port (3 attempts). The captured log tail is part of the failure."""
    log_path = tmp_path / "api.log"
    for attempt in range(1, 4):
        port = _free_port()
        base_url = f"http://127.0.0.1:{port}"
        with log_path.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        client = ContractClient(base_url)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                status, _, body = client.request("GET", "/api/v1/health", retries=0)
            except (OSError, URLError):
                status, body = None, None
            if status == 200 and body == {"status": "ok"}:
                return process, client, log_path
            time.sleep(0.2)
        _stop(process)
    log_tail = log_path.read_text(encoding="utf-8")[-2000:]
    raise AssertionError(
        f"fresh app did not become healthy on 3 ports within 20 s each; last log:\n{log_tail}"
    )


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


@pytest.fixture
def live_api(tmp_path: Path):
    data_dir = tmp_path / "astro-data"
    data_dir.mkdir()
    env = dict(os.environ)
    env.update(
        SECRET_KEY=secrets.token_hex(32),
        FIELD_KEY=Fernet.generate_key().decode("ascii"),
        DATA_DIR=str(data_dir),
        DATABASE_URL=f"sqlite:///{data_dir / 'astro.db'}",
        ASTRO_DISABLE_WORKER="0",
        MONITOR_SERIAL_PORT="",
        PYTHONDONTWRITEBYTECODE="1",
    )
    migrated = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if migrated.returncode:
        _record_mismatch(
            "start API on a fresh isolated database",
            "Alembic upgrade head succeeds",
            f"exit={migrated.returncode}; stdout={migrated.stdout[-1000:]!r}; stderr={migrated.stderr[-1000:]!r}",
        )
    assert migrated.returncode == 0, f"fresh DB migration failed:\n{migrated.stdout}\n{migrated.stderr}"

    process, client, log_path = _spawn_api(env, tmp_path)
    try:
        assert process.poll() is None, f"app exited during startup; see {log_path}"
        yield client, data_dir
    finally:
        _stop(process)


def test_api_contract_endpoints_and_bad_inputs(live_api) -> None:
    client, data_dir = live_api

    # App origin and static demo described by the contract.
    status, headers, _ = client.request("GET", "/")
    _check("GET /", "200 app page or 307/308 redirect to /demo/", str(status), status in (200, 307, 308))
    if status in (307, 308):
        _check("GET / Location", "/demo/", str(headers.get("Location")), headers.get("Location", "").endswith("/demo/"))
    status, _, _ = client.request("GET", "/demo/")
    _check("GET /demo/", "200", str(status), status == 200)

    # Signup is setup for the authenticated contract flows.
    status, _, signup = client.request(
        "POST", "/api/v1/auth/signup", {"email": "contract@example.test", "password": "contract-test-password"}
    )
    _check("POST /api/v1/auth/signup (setup)", "201 with access_token", repr(signup), status == 201 and isinstance(signup, dict) and bool(signup.get("access_token")))
    token = signup["access_token"]

    # Nightly job submission and polling.
    invalid_jobs = [
        ("missing kind", {}),
        ("null params", {"kind": "run_nightly", "params": None}),
        ("wrong params type", {"kind": "run_nightly", "params": "2026-11-12"}),
        ("missing date", {"kind": "run_nightly", "params": {}}),
        ("null date", {"kind": "run_nightly", "params": {"date": None}}),
        ("wrong date", {"kind": "run_nightly", "params": {"date": "not-a-date"}}),
    ]
    for label, body in invalid_jobs:
        status, _, result = client.request("POST", "/api/v1/jobs/process", body, token)
        expected = "400 or 422 error response"
        _check(f"POST /api/v1/jobs/process ({label})", expected, f"{status} {result!r}", status in (400, 422))

    night_request = {"kind": "run_nightly", "params": {"date": "2026-11-12"}}
    job_ids = []
    for attempt in (1, 2):
        status, _, created = client.request("POST", "/api/v1/jobs/process", night_request, token)
        _check(
            f"POST /api/v1/jobs/process (night submission {attempt})",
            "202 with id and status queued/running/succeeded",
            f"{status} {created!r}",
            status == 202 and isinstance(created, dict) and bool(created.get("id")) and created.get("status") in {"queued", "running", "succeeded"},
        )
        job_ids.append(created["id"])

    for job_id in job_ids:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            status, _, job = client.request("GET", f"/api/v1/jobs/{job_id}", token=token)
            if status == 200 and job.get("status") in {"succeeded", "failed"}:
                break
            time.sleep(0.1)
        _check(
            f"GET /api/v1/jobs/{job_id}",
            "200 with id, kind, status, code_version, started, finished; nightly job succeeds",
            f"{status} {job!r}",
            status == 200
            and {"id", "kind", "status", "code_version", "started", "finished"} <= set(job)
            and job.get("status") == "succeeded",
        )

    status, _, unknown_job = client.request("GET", "/api/v1/jobs/not-a-job", token=token)
    _check("GET /api/v1/jobs/not-a-job", "404 error response", f"{status} {unknown_job!r}", status == 404)

    status, _, today = client.request("GET", "/api/v1/today", token=token)
    required_today = {"date", "latest_night", "flags", "pending_checkins", "checkins_consent", "baselines", "context_engine", "sync_status"}
    _check("GET /api/v1/today", "200 with documented Today fields and context_engine", f"{status} {today!r}", status == 200 and isinstance(today, dict) and required_today <= set(today) and isinstance(today.get("sync_status"), dict))
    _check("GET /api/v1/today.context_engine field", "latest non-crisis engine result object after successful night", repr(today.get("context_engine")), isinstance(today.get("context_engine"), dict))

    # Safety is decided first and surfaced at the top level; storage still follows consent
    # (coord/API_CONTRACT.md "Survey safety response (2026-11-13 contract)"). Values are synthetic.
    crisis_cases = [
        (
            "positive item 9",
            {f"phq9_{i}": 0 for i in range(1, 9)} | {"phq9_9": 1},
            {"ok": True, "show": True, "stored": True, "missing": None, "error": None, "total_none": False},
        ),
        (
            "missing item 9",
            {f"phq9_{i}": 0 for i in range(1, 9)},
            {"ok": True, "show": False, "stored": True, "missing": "phq9_9", "error": None, "total_none": True},
        ),
        (
            "null item 9",
            {f"phq9_{i}": 0 for i in range(1, 9)} | {"phq9_9": None},
            {"ok": False, "show": True, "stored": False, "missing": None, "error": "invalid", "total_none": True},
        ),
        (
            "string item 9",
            {f"phq9_{i}": 0 for i in range(1, 9)} | {"phq9_9": "1"},
            {"ok": True, "show": True, "stored": True, "missing": None, "error": None, "total_none": False},
        ),
    ]
    for label, answers, expected in crisis_cases:
        body = {"instrument_id": "phq9", "answers": answers}
        status, _, result = client.request("POST", "/api/v1/responses", body, token)
        fields_ok = (
            isinstance(result, dict)
            and result.get("ok") is expected["ok"]
            and result.get("safety_screen_required") is True
            and result.get("crisis") is True
            and result.get("missing_safety_item") == expected["missing"]
            and isinstance(result.get("safety"), dict)
            and result["safety"].get("show") is expected["show"]
            and result.get("stored") is expected["stored"]
            and result.get("answers_retained") is False
            and result.get("error") == expected["error"]
            and bool(result.get("id")) is expected["stored"]
            and (result.get("total") is None) is expected["total_none"]
        )
        if expected["missing"]:
            fields_ok = fields_ok and (result.get("scores") or {}).get("incomplete") is True
        _check(
            f"POST /api/v1/responses ({label})",
            "200 safety_screen_required=true; stored with safety_flag when scored, else rejected",
            f"{status} {result!r}",
            status == 200 and fields_ok,
        )

    import sqlite3

    with sqlite3.connect(data_dir / "astro.db") as db:
        response_count = db.execute("SELECT COUNT(*) FROM survey_responses").fetchone()[0]
        flagged_count = db.execute(
            "SELECT COUNT(*) FROM survey_responses WHERE safety_flag = 1"
        ).fetchone()[0]
        routine_checkin_count = db.execute("SELECT COUNT(*) FROM checkins_daily").fetchone()[0]
    _check(
        "POST /api/v1/responses (safety persistence check)",
        "positive/missing/string Item 9 stored with safety_flag=true; null item 9 not stored",
        f"survey_responses={response_count}, safety_flag={flagged_count}, "
        f"checkins_daily={routine_checkin_count}",
        response_count == 3 and flagged_count == 3 and routine_checkin_count == 0,
    )

    bad_responses = [
        ("missing body fields", {"instrument_id": "phq9"}),
        ("null answers", {"instrument_id": "phq9", "answers": None}),
        ("wrong answers type", {"instrument_id": "phq9", "answers": [0, 0, 0]}),
        ("wrong instrument type", {"instrument_id": 7, "answers": {}}),
    ]
    for label, body in bad_responses:
        status, _, result = client.request("POST", "/api/v1/responses", body, token)
        _check(f"POST /api/v1/responses ({label})", "422 validation response", f"{status} {result!r}", status == 422)

    # Duplicate submissions must leave one user/date record.
    db_path = data_dir / "astro.db"
    with sqlite3.connect(db_path) as db:
        rows = db.execute(
            "SELECT COUNT(*) FROM context_engine_nights WHERE date = ?",
            ("2026-11-12",),
        ).fetchone()[0]
    _check("duplicate nightly submissions", "one context_engine_nights row for user/date", str(rows), rows == 1)


def test_station_time_and_monitor_contract(live_api) -> None:
    client, _data_dir = live_api

    status, _, body = client.request("GET", "/api/v1/me")
    _check(
        "GET /api/v1/me without token",
        "401 unauthorized error response",
        f"{status} {body!r}",
        status == 401 and isinstance(body, dict) and body.get("error") == "unauthorized",
    )

    status, _, signup = client.request(
        "POST", "/api/v1/auth/signup", {"email": "time@example.test", "password": "contract-test-password"}
    )
    _check("POST /api/v1/auth/signup (station time setup)", "201 with access_token", repr(signup), status == 201)
    token = signup["access_token"]

    status, _, me = client.request("GET", "/api/v1/me", token=token)
    _check(
        "GET /api/v1/me station_time_offset_min default",
        "200 with null (UTC)",
        f"{status} {me!r}",
        status == 200 and isinstance(me, dict) and me.get("station_time_offset_min") is None,
    )

    status, _, patched = client.request("PATCH", "/api/v1/me", {"station_time_offset_min": 330}, token)
    _check(
        "PATCH /api/v1/me station_time_offset_min=330",
        "200 with station_time_offset_min 330",
        f"{status} {patched!r}",
        status == 200 and isinstance(patched, dict) and patched.get("station_time_offset_min") == 330,
    )
    status, _, me = client.request("GET", "/api/v1/me", token=token)
    _check(
        "GET /api/v1/me reads back station_time_offset_min",
        "200 with 330",
        f"{status} {me!r}",
        status == 200 and isinstance(me, dict) and me.get("station_time_offset_min") == 330,
    )

    status, _, cleared = client.request("PATCH", "/api/v1/me", {"station_time_offset_min": None}, token)
    _check(
        "PATCH /api/v1/me station_time_offset_min=null",
        "200 with null (cleared to UTC)",
        f"{status} {cleared!r}",
        status == 200 and isinstance(cleared, dict) and cleared.get("station_time_offset_min") is None,
    )
    status, _, me = client.request("GET", "/api/v1/me", token=token)
    _check(
        "GET /api/v1/me after clearing station time",
        "200 with null",
        f"{status} {me!r}",
        status == 200 and isinstance(me, dict) and me.get("station_time_offset_min") is None,
    )

    status, _, body = client.request("PATCH", "/api/v1/me", {"station_time_offset_min": 841}, token)
    _check(
        "PATCH /api/v1/me station_time_offset_min=841",
        "422 validation response (allowed range is -720..840)",
        f"{status} {body!r}",
        status == 422,
    )

    # Monitor sessions (INTEGRATION_PLAN.md §7): no receiver configured in this fixture.
    status, _, body = client.request("GET", "/api/v1/monitor/sessions")
    _check(
        "GET /api/v1/monitor/sessions without token",
        "401 unauthorized error response",
        f"{status} {body!r}",
        status == 401 and isinstance(body, dict) and body.get("error") == "unauthorized",
    )
    status, _, body = client.request("POST", "/api/v1/monitor/sessions", {"mode": "heart_rate"})
    _check(
        "POST /api/v1/monitor/sessions without token",
        "401 unauthorized error response",
        f"{status} {body!r}",
        status == 401 and isinstance(body, dict) and body.get("error") == "unauthorized",
    )

    status, _, sessions = client.request("GET", "/api/v1/monitor/sessions", token=token)
    _check(
        "GET /api/v1/monitor/sessions (empty)",
        "200 []",
        f"{status} {sessions!r}",
        status == 200 and sessions == [],
    )

    status, _, body = client.request("POST", "/api/v1/monitor/sessions", {"mode": "heart_rate"}, token)
    _check(
        "POST /api/v1/monitor/sessions with no receiver",
        "503 error no_receiver",
        f"{status} {body!r}",
        status == 503 and isinstance(body, dict) and body.get("error") == "no_receiver",
    )

    status, _, body = client.request("GET", "/api/v1/monitor/sessions/not-a-session", token=token)
    _check(
        "GET /api/v1/monitor/sessions/{unknown}",
        "404 error not_found",
        f"{status} {body!r}",
        status == 404 and isinstance(body, dict) and body.get("error") == "not_found",
    )
    status, _, body = client.request("POST", "/api/v1/monitor/sessions/not-a-session/stop", token=token)
    _check(
        "POST /api/v1/monitor/sessions/{unknown}/stop",
        "404 error not_found",
        f"{status} {body!r}",
        status == 404 and isinstance(body, dict) and body.get("error") == "not_found",
    )


def test_spa_deep_links_and_unknown_api(live_api) -> None:
    client, _data_dir = live_api

    status, headers, body = client.request("GET", "/api/v1/nope")
    content_type = headers.get("Content-Type", "")
    _check(
        "GET /api/v1/nope",
        "404 JSON error response",
        f"{status} {content_type!r} {body!r}",
        status == 404 and "json" in content_type.lower() and isinstance(body, dict) and bool(body.get("error")),
    )

    app_dir = ROOT / "backend" / "static" / "app"
    if not app_dir.is_dir():
        pytest.skip("backend/static/app is not built")
    for route in ("/body", "/monitor", "/settings"):
        status, headers, body = client.request("GET", route)
        content_type = headers.get("Content-Type", "")
        _check(
            f"GET {route} deep link",
            "200 HTML (single-page fallback)",
            f"{status} {content_type!r}",
            status == 200 and "html" in content_type.lower() and isinstance(body, str) and "<div id=\"root\"" in body,
        )

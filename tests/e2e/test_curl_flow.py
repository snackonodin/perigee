"""Opt-in e2e: boot the API on a free port with a throwaway DB, run tests/e2e/curl_flow.sh.

Run with:  E2E=1 pytest tests/e2e/test_curl_flow.py
Skipped by default (it starts a server and takes a few seconds). No fixed paths or ports.
The catalog is loaded here explicitly because nothing on main loads it at startup yet.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from csi_core.config import ROOT

SCRIPT = ROOT / "tests" / "e2e" / "curl_flow.sh"
pytestmark = pytest.mark.skipif(
    os.environ.get("E2E") != "1" or shutil.which("curl") is None or shutil.which("bash") is None,
    reason="set E2E=1 (needs bash + curl)",
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _env(data: Path) -> dict[str, str]:
    from cryptography.fernet import Fernet

    env = dict(os.environ)
    env.update(
        SECRET_KEY=os.urandom(32).hex(),
        FIELD_KEY=Fernet.generate_key().decode(),
        DATA_DIR=str(data),
        DATABASE_URL=f"sqlite:///{data / 'astro.db'}",
        PYTHONDONTWRITEBYTECODE="1",
    )
    return env


def test_curl_flow(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    env = _env(data)
    py = sys.executable
    if (ROOT / "alembic.ini").exists():
        subprocess.run([py, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env,
                       check=True, capture_output=True)
    subprocess.run(
        [py, "-c",
         "from sqlalchemy.orm import Session\n"
         "from backend.db import get_engine\n"
         "from backend.services import surveys\n"
         "with Session(get_engine()) as db:\n"
         "    surveys.load_catalog(db); db.commit()\n"],
        cwd=ROOT, env=env, check=True, capture_output=True,
    )
    port = _free_port()
    log = (tmp_path / "server.log").open("w")
    srv = subprocess.Popen(
        [py, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(f"{base}/api/v1/health", timeout=1)
                break
            except OSError:
                time.sleep(0.25)
        p = subprocess.run(["bash", str(SCRIPT)], env={**env, "BASE_URL": base, "PYTHON": py},
                           capture_output=True, text=True, timeout=120)
    finally:
        srv.terminate()
        srv.wait(timeout=10)
        log.close()
    assert p.returncode == 0, p.stdout + p.stderr
    assert "FAIL" not in p.stdout
    server_log = (tmp_path / "server.log").read_text()
    assert env["SECRET_KEY"] not in server_log
    assert "phq9_9" not in server_log  # answers and item keys stay out of logs

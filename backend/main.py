"""FastAPI app. Routers from each workstream are mounted here by the coordinator."""

from __future__ import annotations

import subprocess

from fastapi import FastAPI

from csi_core.config import ROOT

app = FastAPI(title="Astronaut Health Monitor API", version="0.1.0")


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return "unknown"


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/version")
def version() -> dict[str, str]:
    return {"api": "v1", "app": app.version, "code_version": _git_sha()}

"""FastAPI app: startup wiring and router mounting (coordinator-owned).

Workstreams expose APIRouter objects with prefix "/api/v1"; they are mounted
here via ROUTER_MODULES so a missing module (not merged yet) never breaks startup.
"""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from backend.errors import install_error_handlers
from backend.logging import configure_logging
from csi_core.config import ROOT

log = logging.getLogger(__name__)

# module path -> attribute holding the APIRouter
ROUTER_MODULES: list[tuple[str, str]] = [
    ("backend.api.v1.auth", "router"),
    ("backend.api.v1.me", "router"),
    ("backend.api.v1.instruments", "router"),
    ("backend.api.v1.responses", "router"),
    ("backend.api.v1.sessions", "router"),
    ("backend.api.v1.nights", "router"),
    ("backend.api.v1.jobs", "router"),
    ("backend.api.v1.guidance", "router"),
    ("backend.api.v1.today", "router"),
    ("backend.api.v1.ingest", "router"),
    ("backend.api.v1.live", "router"),
    ("backend.api.v1.monitor", "router"),
]


def _git_sha() -> str:
    env = os.environ.get("ASTRO_CODE_VERSION")
    if env:
        return env
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return "unknown"


def mount_routers(app: FastAPI) -> list[str]:
    mounted = []
    for mod_name, attr in ROUTER_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError as e:
            if e.name == mod_name:  # module not written/merged yet: skip quietly
                continue
            raise
        router = getattr(mod, attr)
        if not isinstance(router, APIRouter):
            raise TypeError(f"{mod_name}.{attr} is not an APIRouter")
        app.include_router(router)
        mounted.append(mod_name)
    return mounted


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from sqlalchemy import inspect

    from backend import worker
    from backend.db import SessionLocal, init_db
    from backend.services.guidance import load_guidance_cards
    from backend.services.surveys import load_catalog

    configure_logging()
    engine = init_db()
    if not inspect(engine).has_table("instrument_catalog"):
        raise RuntimeError("database schema missing: run `alembic upgrade head` first")
    with SessionLocal() as db:  # idempotent seed upserts from seeds/
        load_catalog(db)
        load_guidance_cards(db)
        db.commit()
    run_worker = os.environ.get("ASTRO_DISABLE_WORKER") != "1"
    if run_worker:
        worker.start_worker()
    log.info("api started", extra={"routers": len(app.state.mounted), "worker": run_worker})
    try:
        yield
    finally:
        if run_worker:
            worker.stop_worker()


def create_app(*, with_lifespan: bool = True) -> FastAPI:
    app = FastAPI(
        title="Astronaut Health Monitor API",
        version="0.1.0",
        lifespan=lifespan if with_lifespan else None,
    )
    install_error_handlers(app)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/version")
    def version() -> dict[str, str]:
        return {"api": "v1", "app": app.version, "code_version": _git_sha()}

    app.state.mounted = mount_routers(app)

    demo_dir = ROOT / "backend" / "static" / "demo"
    if demo_dir.is_dir():  # offline demo page (same origin as the API)
        from fastapi.staticfiles import StaticFiles

        app.mount("/demo", StaticFiles(directory=demo_dir, html=True), name="demo")
    frontend_dir = ROOT / "backend" / "static" / "app"
    if frontend_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    else:
        from fastapi.responses import RedirectResponse

        @app.get("/", include_in_schema=False)
        def root() -> RedirectResponse:
            return RedirectResponse(url="/demo/")
    return app


app = create_app()

"""Cryptopia backend entrypoint.

Composes:

* The Cryptopia REST API (``/api/...``).
* The per-notebook ``marimo edit`` HTTP/WS reverse proxy at ``/api/edit/...``.
* The marimo run-mode ASGI mount at ``/run/...`` (with permission gating).
* The static public bundle route at ``/p/<id>/...``.
* The SvelteKit frontend (built into ``frontend/build``) at ``/``, if present.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import edit_proxy, me, notebooks, public_static
from app.api.run_mount import build_run_app
from app.core.config import get_settings
from app.services.edit_sessions import edit_session_manager

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
LOG = logging.getLogger("cryptopia")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
    await edit_session_manager.startup()
    LOG.info(
        "Cryptopia ready (data_dir=%s, public_url=%s, authelia=%s)",
        settings.data_dir,
        settings.public_url,
        settings.authelia_url,
    )
    try:
        yield
    finally:
        await edit_session_manager.shutdown()
        await edit_proxy.shutdown_http_client()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Cryptopia",
        description="A marimo-powered modern data dashboard platform",
        version="0.1.0",
        lifespan=lifespan,
        # We sit behind a reverse proxy that does Authelia forward-auth,
        # so we DO NOT want to expose the OpenAPI / docs by default; the
        # platform UI is the contract surface, not raw HTTP.
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    # ---- API ---------------------------------------------------------------
    app.include_router(me.router, prefix="/api")
    app.include_router(notebooks.router, prefix="/api/notebooks")
    app.include_router(edit_proxy.router, prefix="/api")

    # ---- Public static (WASM bundle) ---------------------------------------
    app.include_router(public_static.router)

    # ---- Marimo run mount (interactive, gated) -----------------------------
    # The dynamic-directory builder handles ".py" lookup + per-request
    # validation. We mount it at /run; the builder is configured with the
    # same base path so its internal URL rewriting agrees with our mount.
    app.mount("/run", build_run_app(settings))

    # ---- Frontend ----------------------------------------------------------
    frontend_dir = settings.data_dir.parent / "frontend" / "build"
    if frontend_dir.is_dir():
        # Mount last so it's used as a fallback for paths the API didn't claim.
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


app = create_app()

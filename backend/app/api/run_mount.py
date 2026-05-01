"""Mount the marimo run-mode ASGI app at ``/run/<notebook_id>/...``.

We use marimo's :func:`create_asgi_app` + ``with_dynamic_directory`` so the
underlying notebook process pool is shared across all published notebooks
(rather than running one Python interpreter per notebook).

Permissioning is a thin wrapper around our own ``can_run`` /
``can_view_static`` rules: the ``validate_callback`` is invoked on every
HTTP/WebSocket request before the request reaches marimo's internals, and
returning ``False`` short-circuits with a 404.
"""

from __future__ import annotations

import logging

from marimo._server.asgi import create_asgi_app
from sqlalchemy import select
from starlette.types import ASGIApp, Scope

from app.core.auth import AuthIdentity, extract_identity
from app.core.config import Settings
from app.db.base import SessionLocal
from app.models.notebook import Notebook
from app.services import notebooks as nb_service

LOG = logging.getLogger(__name__)


async def _validate(app_path: str, scope: Scope) -> bool:
    """Return True iff the requesting identity may interact with the app."""
    notebook_id = app_path.split("/", 1)[0]
    if not notebook_id:
        return False

    # We need a Request-like object for extract_identity. Build a tiny shim
    # exposing ``headers`` since that's all extract_identity reads.
    class _ScopeShim:
        def __init__(self, scope: Scope) -> None:
            from starlette.datastructures import Headers

            self.headers = Headers(scope=scope)

    identity: AuthIdentity | None = extract_identity(_ScopeShim(scope))  # type: ignore[arg-type]

    async with SessionLocal() as session:
        stmt = select(Notebook).where(Notebook.id == notebook_id)
        nb = (await session.execute(stmt)).scalar_one_or_none()
        if nb is None:
            return False
        # selectinload would be cleaner, but we only need the owner's
        # username for the permission check, which is keyed on identity.
        await session.refresh(nb, ["owner"])
        return nb_service.can_run(nb, identity)


def build_run_app(settings: Settings) -> ASGIApp:
    """Build the marimo run-mode ASGI app for ``settings``."""
    builder = create_asgi_app(quiet=True, include_code=False).with_dynamic_directory(
        path="/run",
        directory=str(settings.published_dir),
        validate_callback=_validate,
    )
    return builder.build()


__all__ = ["build_run_app"]

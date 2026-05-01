"""Serves the WASM-rendered static bundle for public notebooks at ``/p/<id>/...``.

This path is intentionally allowed to bypass authentication when the
notebook's visibility is ``public`` — that way external sharing / link
preview / embedding works without forcing a login. Anything that requires
backend resources lives behind the authenticated ``/run`` mount instead.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

from app.core.auth import AuthIdentity, get_optional_identity
from app.core.config import Settings, get_settings
from app.db.base import SessionLocal
from app.services import notebooks as nb_service

router = APIRouter()


def _safe_resolve(root: Path, requested: str) -> Path | None:
    """Resolve ``requested`` under ``root`` while refusing path-traversal."""
    target = (root / requested).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    return target


@router.get("/p/{notebook_id}", include_in_schema=False)
async def public_static_root_redirect(notebook_id: str) -> RedirectResponse:
    return RedirectResponse(url=f"/p/{notebook_id}/", status_code=307)


@router.get("/p/{notebook_id}/", include_in_schema=False)
@router.get("/p/{notebook_id}/{path:path}", include_in_schema=False)
async def public_static(
    notebook_id: str,
    request: Request,
    path: str = "",
    identity: AuthIdentity | None = Depends(get_optional_identity),
    settings: Settings = Depends(get_settings),
) -> Response:
    async with SessionLocal() as session:
        nb = await nb_service.get_by_id(session, notebook_id)
    if nb is None:
        raise HTTPException(status_code=404)

    if not nb_service.can_view_static(nb, identity):
        # For TEAM notebooks we want logged-in non-members to see a 404
        # rather than an obvious "permission denied" leak.
        if identity is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        raise HTTPException(status_code=404)

    static_root = nb_service.static_dir_path(nb.id, settings)
    if not static_root.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Static bundle is still being rendered. Try again in a moment.",
        )

    relative = path or "index.html"
    if relative.endswith("/"):
        relative = relative + "index.html"
    target = _safe_resolve(static_root, relative)
    if target is None or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)

    return FileResponse(target)

"""HTTP API for managing notebooks (metadata, lifecycle, sharing)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AuthIdentity,
    get_optional_identity,
    require_identity,
)
from app.core.config import Settings, get_settings
from app.db.base import get_session
from app.models.notebook import Notebook, NotebookVersion
from app.schemas.notebook import (
    NotebookCreate,
    NotebookDetail,
    NotebookSummary,
    NotebookUpdate,
    NotebookVersionInfo,
    PublishResponse,
    UserPublic,
)
from app.services import notebooks as nb_service
from app.services import users as user_service

router = APIRouter()


def _to_summary(nb: Notebook) -> NotebookSummary:
    return NotebookSummary(
        id=nb.id,
        slug=nb.slug,
        title=nb.title,
        description=nb.description,
        visibility=nb.visibility,
        allowed_groups=list(nb.allowed_groups or []),
        owner=UserPublic.model_validate(nb.owner),
        created_at=nb.created_at,
        updated_at=nb.updated_at,
        published_at=nb.published_at,
        published_version=nb.published_version,
    )


def _to_detail(nb: Notebook, identity: AuthIdentity | None) -> NotebookDetail:
    base = _to_summary(nb)
    return NotebookDetail(
        **base.model_dump(),
        can_edit=nb_service.can_edit(nb, identity),
        can_run=nb_service.can_run(nb, identity),
        is_published=nb.published_version is not None,
    )


async def _load_notebook_or_404(
    session: AsyncSession, notebook_id: str
) -> Notebook:
    nb = await nb_service.get_by_id(session, notebook_id)
    if nb is None:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return nb


def _ensure_view(nb: Notebook, identity: AuthIdentity | None) -> None:
    if nb_service.can_edit(nb, identity):
        return
    if identity is None:
        if nb.visibility.value == "public" and nb.published_version is not None:
            return
        raise HTTPException(status_code=401, detail="Authentication required")
    if nb_service.can_run(nb, identity):
        return
    if nb_service.can_view_static(nb, identity):
        return
    raise HTTPException(status_code=404, detail="Notebook not found")


def _ensure_edit(nb: Notebook, identity: AuthIdentity) -> None:
    if not nb_service.can_edit(nb, identity):
        raise HTTPException(status_code=403, detail="Only the owner can modify this notebook")


# ---------------------------------------------------------------------------
# Listing


@router.get("", response_model=list[NotebookSummary])
async def list_notebooks(
    mine: bool = False,
    identity: AuthIdentity | None = Depends(get_optional_identity),
    session: AsyncSession = Depends(get_session),
) -> list[NotebookSummary]:
    if mine and identity is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    rows = await nb_service.list_visible(session, identity, owned_only=mine)
    return [_to_summary(nb) for nb in rows]


# ---------------------------------------------------------------------------
# Create / read / update / delete


@router.post("", response_model=NotebookDetail, status_code=status.HTTP_201_CREATED)
async def create_notebook(
    payload: NotebookCreate,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> NotebookDetail:
    user = await user_service.upsert_from_identity(session, identity)
    nb = await nb_service.create(
        session,
        user,
        title=payload.title,
        slug=payload.slug,
        description=payload.description,
        visibility=payload.visibility,
        allowed_groups=payload.allowed_groups,
    )
    await session.commit()
    await session.refresh(nb, ["owner"])
    return _to_detail(nb, identity)


@router.get("/{notebook_id}", response_model=NotebookDetail)
async def get_notebook(
    notebook_id: str,
    identity: AuthIdentity | None = Depends(get_optional_identity),
    session: AsyncSession = Depends(get_session),
) -> NotebookDetail:
    nb = await _load_notebook_or_404(session, notebook_id)
    _ensure_view(nb, identity)
    return _to_detail(nb, identity)


@router.patch("/{notebook_id}", response_model=NotebookDetail)
async def update_notebook(
    notebook_id: str,
    payload: NotebookUpdate,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> NotebookDetail:
    nb = await _load_notebook_or_404(session, notebook_id)
    _ensure_edit(nb, identity)
    await nb_service.update_metadata(
        session,
        nb,
        title=payload.title,
        description=payload.description,
        visibility=payload.visibility,
        allowed_groups=payload.allowed_groups,
    )
    await session.commit()
    return _to_detail(nb, identity)


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook(
    notebook_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> None:
    nb = await _load_notebook_or_404(session, notebook_id)
    _ensure_edit(nb, identity)
    await nb_service.delete(session, nb)
    await session.commit()


# ---------------------------------------------------------------------------
# Publishing


@router.post("/{notebook_id}/publish", response_model=PublishResponse)
async def publish_notebook(
    notebook_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PublishResponse:
    nb = await _load_notebook_or_404(session, notebook_id)
    _ensure_edit(nb, identity)

    user = await user_service.upsert_from_identity(session, identity)
    try:
        version = await nb_service.publish(session, nb, user, settings=settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()

    static_url = (
        f"/p/{nb.id}/" if nb.visibility.value == "public" else None
    )
    return PublishResponse(
        notebook_id=nb.id,
        version=version.version,
        published_at=version.published_at,
        static_url=static_url,
        run_url=f"/run/{nb.id}/",
    )


@router.post("/{notebook_id}/unpublish", status_code=status.HTTP_204_NO_CONTENT)
async def unpublish_notebook(
    notebook_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> None:
    nb = await _load_notebook_or_404(session, notebook_id)
    _ensure_edit(nb, identity)
    await nb_service.unpublish(session, nb)
    await session.commit()


@router.get("/{notebook_id}/versions", response_model=list[NotebookVersionInfo])
async def list_versions(
    notebook_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> list[NotebookVersionInfo]:
    from sqlalchemy import select

    nb = await _load_notebook_or_404(session, notebook_id)
    _ensure_edit(nb, identity)
    stmt = (
        select(NotebookVersion)
        .where(NotebookVersion.notebook_id == nb.id)
        .order_by(NotebookVersion.version.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [NotebookVersionInfo.model_validate(v) for v in rows]

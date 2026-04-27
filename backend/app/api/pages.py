"""
Pages API: list / get / create / update / delete / import / export, plus the
HTTP execution endpoints (`/run-cell`, `/dispatch`) that drive interactivity.

There is no WebSocket — runtime interaction is exclusively code-cell-shaped:
the frontend POSTs a cell run or a widget dispatch and gets back a complete
output list.
"""
import json
import re

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.models.page import Page, Tag
from app.models.user import User
from app.services import extended_md
from app.services.execution import (
    dispatch_widget,
    kernel_pool,
    run_single_cell,
)

router = APIRouter(prefix="/api/pages", tags=["pages"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class PageCreate(BaseModel):
    title: str | None = None
    source_md: str = ""


class PageUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    source_md: str | None = None
    is_draft: bool | None = None


class RunCellRequest(BaseModel):
    cell_id: str
    widget_values: dict = {}


class DispatchRequest(BaseModel):
    widget_id: str
    value: object = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def page_to_dict(p: Page, *, include_source: bool = False) -> dict:
    out = {
        "id": p.id,
        "slug": p.slug,
        "title": p.title,
        "description": p.description,
        "author_username": p.author.username,
        "author_full_name": p.author.full_name,
        "is_interactive": p.is_interactive,
        "is_draft": p.is_draft,
        "published_at": p.published_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
        "tags": [t.name for t in p.tags],
    }
    if include_source:
        out["source_md"] = p.source_md
    return out


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\-_]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "page"


async def unique_slug(db: AsyncSession, author_id: int, base: str, *, exclude_id: int | None = None) -> str:
    candidate = base
    n = 2
    while True:
        q = select(Page.id).where(Page.author_id == author_id, Page.slug == candidate)
        if exclude_id is not None:
            q = q.where(Page.id != exclude_id)
        existing = await db.execute(q)
        if existing.scalar_one_or_none() is None:
            return candidate
        candidate = f"{base}-{n}"
        n += 1


async def resolve_tags(db: AsyncSession, names: list[str]) -> list[Tag]:
    """Look up or create Tag rows for the given names."""
    tags: list[Tag] = []
    for name in names:
        clean = name.strip()
        if not clean:
            continue
        result = await db.execute(select(Tag).where(Tag.name == clean))
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(name=clean)
            db.add(tag)
            await db.flush()
        tags.append(tag)
    return tags


async def sync_tags(db: AsyncSession, page: Page, names: list[str]) -> None:
    """Replace `page.tags` with rows resolved from `names`. The caller must
    ensure `page.tags` is loaded (e.g. via selectinload, or by being a
    transient object that has not been refreshed yet)."""
    tags = await resolve_tags(db, names)
    # For a freshly added Page that has not yet been refreshed, the relationship
    # collection is initialised empty; assigning replaces it without triggering
    # a lazy load.
    page.tags = tags


async def refresh_metadata(db: AsyncSession, page: Page, source_md: str) -> None:
    """Recompute derived fields from source_md and persist them on the page."""
    meta = extended_md.derive_metadata(source_md)
    if meta["title"]:
        page.title = meta["title"]
    page.description = meta["description"]
    page.is_interactive = meta["is_interactive"]
    page.source_md = source_md
    if meta["tags"]:
        await sync_tags(db, page, meta["tags"])


# ---------------------------------------------------------------------------
# Listing endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_pages(
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=50),
    q: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Page)
        .options(selectinload(Page.author), selectinload(Page.tags))
        .where(Page.is_draft.is_(False))
        .order_by(Page.published_at.desc())
    )
    if q:
        like = f"%{q}%"
        query = query.where(or_(Page.title.ilike(like), Page.description.ilike(like)))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    offset = (page - 1) * per_page
    result = await db.execute(query.offset(offset).limit(per_page))
    items = result.scalars().all()
    return {"items": [page_to_dict(p) for p in items], "total": total, "page": page}


@router.get("/my")
async def my_pages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.author), selectinload(Page.tags))
        .where(Page.author_id == current_user.id)
        .order_by(Page.updated_at.desc())
    )
    items = result.scalars().all()
    return [page_to_dict(p) for p in items]


@router.get("/{username}/{slug}")
async def get_page(username: str, slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.author), selectinload(Page.tags))
        .join(User, Page.author_id == User.id)
        .where(User.username == username.lower(), Page.slug == slug, Page.is_draft.is_(False))
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Page not found")
    return page_to_dict(p, include_source=True)


@router.get("/{username}/{slug}/raw.md", response_class=PlainTextResponse)
async def get_page_raw(username: str, slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.author), selectinload(Page.tags))
        .join(User, Page.author_id == User.id)
        .where(User.username == username.lower(), Page.slug == slug, Page.is_draft.is_(False))
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Page not found")
    return PlainTextResponse(p.source_md, media_type="text/markdown; charset=utf-8")


# ---------------------------------------------------------------------------
# Owned pages — read by id (for the editor)
# ---------------------------------------------------------------------------

@router.get("/id/{page_id}")
async def get_page_by_id(
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.author), selectinload(Page.tags))
        .where(Page.id == page_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Page not found")
    if p.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the author")
    return page_to_dict(p, include_source=True)


# ---------------------------------------------------------------------------
# Create / update / delete
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def create_page(
    payload: PageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = payload.source_md or ""
    meta = extended_md.derive_metadata(source)
    title = payload.title or meta["title"] or "Untitled"
    base_slug = slugify(title)
    slug = await unique_slug(db, current_user.id, base_slug)
    tags = await resolve_tags(db, meta["tags"])

    page = Page(
        slug=slug,
        title=title,
        description=meta["description"],
        author_id=current_user.id,
        is_interactive=meta["is_interactive"],
        source_md=source,
        is_draft=True,
        tags=tags,
    )
    db.add(page)
    await db.flush()
    await db.refresh(page, ["author", "tags"])
    return page_to_dict(page, include_source=True)


@router.put("/id/{page_id}")
async def update_page(
    page_id: int,
    payload: PageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.tags), selectinload(Page.author))
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    if page.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the author")

    if payload.source_md is not None:
        await refresh_metadata(db, page, payload.source_md)
        # Reset the kernel so widget state from a previous version doesn't leak.
        await kernel_pool.reset(page.id)

    if payload.title is not None:
        page.title = payload.title.strip() or page.title
        # Re-slug if the page is still a draft.
        if page.is_draft:
            base = slugify(page.title)
            page.slug = await unique_slug(db, current_user.id, base, exclude_id=page.id)

    if payload.description is not None:
        page.description = payload.description.strip() or None

    if payload.tags is not None:
        await sync_tags(db, page, payload.tags)

    if payload.is_draft is not None:
        was_draft = page.is_draft
        page.is_draft = payload.is_draft
        if was_draft and not payload.is_draft:
            # Publishing for the first time — finalize the slug against published peers.
            base = slugify(page.title)
            page.slug = await unique_slug(db, current_user.id, base, exclude_id=page.id)

    await db.flush()
    await db.refresh(page, ["author", "tags"])
    return page_to_dict(page, include_source=True)


@router.delete("/id/{page_id}", status_code=204)
async def delete_page(
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Page).where(Page.id == page_id))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    if page.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the author")
    await db.delete(page)
    await kernel_pool.reset(page_id)


# ---------------------------------------------------------------------------
# Import .md / .ipynb
# ---------------------------------------------------------------------------

@router.post("/import", status_code=201)
async def import_page(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8")

    name = (file.filename or "").lower()
    if name.endswith(".ipynb"):
        try:
            nb = json.loads(text)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid notebook JSON: {e}")
        source_md = extended_md.from_nbformat(nb)
    else:
        source_md = text

    meta = extended_md.derive_metadata(source_md)
    title = meta["title"] or (file.filename or "Imported page").rsplit(".", 1)[0]
    base = slugify(title)
    slug = await unique_slug(db, current_user.id, base)
    tags = await resolve_tags(db, meta["tags"])

    page = Page(
        slug=slug,
        title=title,
        description=meta["description"],
        author_id=current_user.id,
        is_interactive=meta["is_interactive"],
        source_md=source_md,
        is_draft=True,
        tags=tags,
    )
    db.add(page)
    await db.flush()
    await db.refresh(page, ["author", "tags"])
    return page_to_dict(page, include_source=True)


# ---------------------------------------------------------------------------
# Runtime execution endpoints
# ---------------------------------------------------------------------------
#
# Two HTTP shapes drive every runtime interaction:
#
#   POST /id/{page_id}/run-cell  — execute one code cell (used by the editor's
#                                  Run button and by the viewer's first run /
#                                  re-run page button).
#   POST /id/{page_id}/dispatch  — invoke the on_change callback registered
#                                  for a widget id during a previous cell run.
#
# Both paths share the persistent per-page kernel from `kernel_pool`. Viewers
# may run cells on published pages anonymously; only the author's request
# additionally splices outputs back into `source_md` (cached output).

async def _load_page_for_run(db: AsyncSession, page_id: int) -> Page:
    result = await db.execute(
        select(Page).options(selectinload(Page.tags)).where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


def _can_run(page: Page, user: User | None) -> bool:
    """Drafts are author-only; published pages are runnable by anyone."""
    if page.is_draft:
        return user is not None and user.id == page.author_id
    return True


@router.post("/id/{page_id}/run-cell")
async def run_cell(
    page_id: int,
    payload: RunCellRequest,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    page = await _load_page_for_run(db, page_id)
    if not _can_run(page, current_user):
        raise HTTPException(status_code=403, detail="Cannot run this page")

    outcome = await run_single_cell(
        page_id=page.id,
        source_md=page.source_md,
        cell_id=payload.cell_id,
        widget_values=payload.widget_values,
    )

    # Only the author's runs persist outputs back into source_md so the
    # cached page stays in their hands. Viewer runs are stateless.
    if current_user is not None and current_user.id == page.author_id:
        new_source = extended_md.splice_output(
            page.source_md, payload.cell_id, outcome["outputs"]
        )
        if new_source != page.source_md:
            await refresh_metadata(db, page, new_source)
            await db.flush()

    return {
        "outputs": outcome["outputs"],
        "error": outcome["error"],
        "source_md": page.source_md,
    }


@router.post("/id/{page_id}/dispatch")
async def dispatch(
    page_id: int,
    payload: DispatchRequest,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    page = await _load_page_for_run(db, page_id)
    if not _can_run(page, current_user):
        raise HTTPException(status_code=403, detail="Cannot run this page")

    outcome = await dispatch_widget(
        page_id=page.id,
        widget_id=payload.widget_id,
        value=payload.value,
    )
    return {"outputs": outcome["outputs"], "error": outcome["error"]}

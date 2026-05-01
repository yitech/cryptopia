"""Notebook service: filesystem layout, slug generation, permission checks,
publish/unpublish, and the WASM static export hand-off.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import shutil
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import AuthIdentity
from app.core.config import Settings, get_settings
from app.models.notebook import Notebook, NotebookVersion, Visibility
from app.models.user import User

LOG = logging.getLogger(__name__)

# Strong references to fire-and-forget tasks (e.g., the WASM export). We
# hold the references until the task completes so Python's garbage
# collector doesn't reap an in-flight subprocess wait.
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()

# Minimal valid marimo notebook used as the seed when a user creates a new
# notebook. Keep it under control instead of relying on `marimo new` because
# we need byte-stable output (no random version banner) and don't want to
# spawn a subprocess just to write a stub file.
_SEED_TEMPLATE = '''# /// script
# requires-python = ">=3.11"
# ///

import marimo

__generated_with = "0.13.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(
        """
        # {title}

        {description}

        Edit this notebook to start your analysis.
        """
    )
    return


if __name__ == "__main__":
    app.run()
'''


# ---------------------------------------------------------------------------
# Slug helpers


def slugify(text: str) -> str:
    """Conservative slug: lowercase ASCII, dashes, max 60 chars."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    text = re.sub(r"-{2,}", "-", text)
    return text[:60] or "notebook"


async def _unique_slug(session: AsyncSession, owner_id: int, base: str) -> str:
    candidate = base
    suffix = 2
    while True:
        stmt = select(Notebook.id).where(
            Notebook.owner_id == owner_id, Notebook.slug == candidate
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


# ---------------------------------------------------------------------------
# Filesystem paths


def working_file_path(notebook: Notebook, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    owner_dir = settings.notebooks_dir / notebook.owner.username
    owner_dir.mkdir(parents=True, exist_ok=True)
    return owner_dir / f"{notebook.id}.py"


def published_file_path(notebook_id: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.published_dir / f"{notebook_id}.py"


def static_dir_path(notebook_id: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.published_static_dir / notebook_id


# ---------------------------------------------------------------------------
# Permission checks


def can_edit(notebook: Notebook, identity: AuthIdentity | None) -> bool:
    return identity is not None and notebook.owner.username == identity.username


def can_run(notebook: Notebook, identity: AuthIdentity | None) -> bool:
    """Whether *identity* may run the published version interactively.

    This is the live, kernel-backed path. Anonymous users never qualify
    (Cryptopia requires a login to use backend resources). Owners always
    qualify; otherwise the visibility rules apply.
    """
    if identity is None:
        return False
    if notebook.published_version is None:
        return False
    if can_edit(notebook, identity):
        return True
    if notebook.visibility == Visibility.PUBLIC:
        return True
    if notebook.visibility == Visibility.TEAM:
        return identity.in_any_group(notebook.allowed_groups or [])
    return False


def can_view_static(notebook: Notebook, identity: AuthIdentity | None) -> bool:
    """Whether *identity* may see the static (read-only WASM) snapshot.

    PUBLIC notebooks are world-readable so anonymous visitors get a
    reasonable preview before being asked to log in for interactivity.
    TEAM notebooks always require the right group, even for the static view.
    """
    if notebook.published_version is None:
        return False
    if notebook.visibility == Visibility.PUBLIC:
        return True
    return can_run(notebook, identity)


# ---------------------------------------------------------------------------
# Lookups


async def list_visible(
    session: AsyncSession,
    identity: AuthIdentity | None,
    *,
    owned_only: bool = False,
) -> list[Notebook]:
    """List notebooks visible to ``identity``.

    Anonymous users only see public notebooks that have been published.
    Logged-in users see: their own + public published + team published
    where they share a group.
    """
    stmt = select(Notebook).options(selectinload(Notebook.owner))

    if owned_only:
        if identity is None:
            return []
        stmt = stmt.where(Notebook.owner.has(User.username == identity.username))
    else:
        if identity is None:
            stmt = stmt.where(
                Notebook.visibility == Visibility.PUBLIC,
                Notebook.published_version.is_not(None),
            )

    rows = (await session.execute(stmt.order_by(Notebook.updated_at.desc()))).scalars().all()
    if owned_only or identity is None:
        return list(rows)

    visible = []
    for nb in rows:
        if nb.owner.username == identity.username:
            visible.append(nb)
        elif nb.published_version is None:
            continue
        elif nb.visibility == Visibility.PUBLIC:
            visible.append(nb)
        elif nb.visibility == Visibility.TEAM and identity.in_any_group(nb.allowed_groups or []):
            visible.append(nb)
    return visible


async def get_by_id(session: AsyncSession, notebook_id: str) -> Notebook | None:
    stmt = (
        select(Notebook)
        .where(Notebook.id == notebook_id)
        .options(selectinload(Notebook.owner))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Mutations


async def create(
    session: AsyncSession,
    owner: User,
    *,
    title: str,
    slug: str | None,
    description: str,
    visibility: Visibility,
    allowed_groups: list[str],
) -> Notebook:
    base = slug or slugify(title)
    final_slug = await _unique_slug(session, owner.id, base)

    notebook = Notebook(
        slug=final_slug,
        title=title,
        description=description,
        owner_id=owner.id,
        visibility=visibility,
        allowed_groups=allowed_groups,
    )
    session.add(notebook)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise

    # Eagerly load owner so working_file_path() works without an extra round-trip.
    notebook.owner = owner
    path = working_file_path(notebook)
    path.write_text(_SEED_TEMPLATE.format(title=title, description=description or ""))
    return notebook


async def update_metadata(
    session: AsyncSession,
    notebook: Notebook,
    *,
    title: str | None = None,
    description: str | None = None,
    visibility: Visibility | None = None,
    allowed_groups: list[str] | None = None,
) -> Notebook:
    if title is not None:
        notebook.title = title
    if description is not None:
        notebook.description = description
    if visibility is not None:
        notebook.visibility = visibility
    if allowed_groups is not None:
        notebook.allowed_groups = allowed_groups
    await session.flush()
    return notebook


async def delete(session: AsyncSession, notebook: Notebook) -> None:
    working = working_file_path(notebook)
    if working.exists():
        working.unlink()
    published = published_file_path(notebook.id)
    if published.exists():
        published.unlink()
    static = static_dir_path(notebook.id)
    if static.exists():
        shutil.rmtree(static, ignore_errors=True)
    await session.delete(notebook)


async def publish(
    session: AsyncSession,
    notebook: Notebook,
    publisher: User,
    *,
    settings: Settings | None = None,
) -> NotebookVersion:
    """Snapshot the current working file as a new version and copy it into
    the public ``published/`` tree. Triggers an async WASM export.
    """
    settings = settings or get_settings()
    working = working_file_path(notebook, settings)
    if not working.exists():
        raise FileNotFoundError(f"Working file missing: {working}")

    content = working.read_text()
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

    next_version = (notebook.published_version or 0) + 1
    version = NotebookVersion(
        notebook_id=notebook.id,
        version=next_version,
        content=content,
        content_hash=digest,
        published_by=publisher.id,
    )
    session.add(version)

    notebook.published_version = next_version
    notebook.published_at = datetime.now(UTC)

    published = published_file_path(notebook.id, settings)
    published.write_text(content)

    await session.flush()

    # Kick off (but don't await) the WASM export. Failing to render the
    # static preview should never block publish — the interactive `/run`
    # path will still work because it reads the same .py file directly.
    task = asyncio.create_task(_export_html_wasm(notebook.id, published, settings))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return version


async def unpublish(session: AsyncSession, notebook: Notebook) -> None:
    notebook.published_version = None
    notebook.published_at = None

    published = published_file_path(notebook.id)
    if published.exists():
        published.unlink()
    static = static_dir_path(notebook.id)
    if static.exists():
        shutil.rmtree(static, ignore_errors=True)
    await session.flush()


async def _export_html_wasm(notebook_id: str, source: Path, settings: Settings) -> None:
    """Render the WASM static bundle for the published notebook.

    We use ``marimo export html-wasm`` so anonymous visitors of public
    notebooks can see and even interact with the notebook entirely
    in-browser, with zero backend exposure.
    """
    out_dir = static_dir_path(notebook_id, settings)
    tmp_dir = out_dir.with_suffix(".tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "marimo",
        "export",
        "html-wasm",
        str(source),
        "-o",
        str(tmp_dir),
        "--mode",
        "run",
    ]
    LOG.info("Exporting WASM bundle for %s: %s", notebook_id, " ".join(cmd))
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            LOG.warning(
                "WASM export failed for %s (rc=%s): %s",
                notebook_id,
                proc.returncode,
                stderr.decode("utf-8", "replace")[:500],
            )
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return
    except Exception:
        LOG.exception("WASM export crashed for %s", notebook_id)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return

    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    tmp_dir.rename(out_dir)
    LOG.info("Wrote WASM bundle for %s -> %s", notebook_id, out_dir)

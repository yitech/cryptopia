"""Notebook + NotebookVersion ORM models.

A *notebook* is a logical entity owned by one user. Its working copy is a
single ``.py`` file written by ``marimo edit`` and lives at
``data/notebooks/<owner>/<id>.py``.

When the owner publishes, we copy the working file into ``data/published/``
and snapshot it into a :class:`NotebookVersion` row. Permissions
(``visibility`` + ``allowed_groups``) are evaluated against the published
copy, so editing a draft never accidentally exposes WIP to viewers.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid.uuid4().hex


class Visibility(enum.StrEnum):
    PUBLIC = "public"  # Anyone can VIEW (anonymous = static; logged-in = interactive)
    TEAM = "team"  # Only logged-in members of allowed_groups


class Notebook(Base):
    __tablename__ = "notebooks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    slug: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    owner: Mapped[User] = relationship("User", back_populates="notebooks")  # noqa: F821

    visibility: Mapped[Visibility] = mapped_column(
        Enum(Visibility, native_enum=False, length=16), default=Visibility.TEAM
    )
    # JSON list of Authelia group names that may access this notebook
    # when visibility == TEAM. Ignored when visibility == PUBLIC.
    allowed_groups: Mapped[list[str]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    published_version: Mapped[int | None] = mapped_column(Integer, default=None)

    versions: Mapped[list[NotebookVersion]] = relationship(
        "NotebookVersion",
        back_populates="notebook",
        cascade="all, delete-orphan",
        order_by="NotebookVersion.version.desc()",
    )

    __table_args__ = (UniqueConstraint("owner_id", "slug", name="uq_notebook_owner_slug"),)


class NotebookVersion(Base):
    __tablename__ = "notebook_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    notebook_id: Mapped[str] = mapped_column(
        ForeignKey("notebooks.id", ondelete="CASCADE"), index=True
    )
    notebook: Mapped[Notebook] = relationship("Notebook", back_populates="versions")

    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    published_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("notebook_id", "version", name="uq_notebook_version"),)

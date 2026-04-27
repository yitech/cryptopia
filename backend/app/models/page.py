from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Integer, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


pages_tags = Table(
    "pages_tags",
    Base.metadata,
    Column("page_id", Integer, ForeignKey("pages.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    pages: Mapped[list["Page"]] = relationship(
        "Page", secondary=pages_tags, back_populates="tags"
    )


class Page(Base):
    """
    A published research page. The canonical artifact is `source_md`, written
    in Cryptopia Extended Markdown (see docs/extended-markdown.md). Outputs of
    runnable code cells live inline in the markdown via `cx-output` fences, so
    a Page row carries everything needed to render the static view.
    """
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_interactive: Mapped[bool] = mapped_column(Boolean, default=False)
    source_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    author: Mapped["User"] = relationship("User", back_populates="pages")  # noqa: F821
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary=pages_tags, back_populates="pages"
    )

"""initial Cryptopia schema with pages

Brings any existing database to the post-redesign schema:
- Creates users / tags / pages / pages_tags / comments / reactions if absent.
- Converts a legacy `research` + `notebooks` schema into the new `pages` table
  (notebook JSON → Cryptopia Extended Markdown via services/extended_md).
- Repoints `comments.research_id` → `comments.page_id` (and same for reactions).
- Drops the obsolete `research`, `notebooks`, and `research_tags` tables.

Revision ID: 0001_initial_pages
Revises: 
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0001_initial_pages"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column("avatar_url", sa.String(length=500), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("username"),
            sa.UniqueConstraint("email"),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_username", "users", ["username"], unique=True)
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if "tags" not in tables:
        op.create_table(
            "tags",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.UniqueConstraint("name"),
        )
        op.create_index("ix_tags_name", "tags", ["name"], unique=True)

    if "pages" not in tables:
        op.create_table(
            "pages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(length=200), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "author_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("is_interactive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("source_md", sa.Text(), nullable=False, server_default=""),
            sa.Column("is_draft", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_pages_id", "pages", ["id"])
        op.create_index("ix_pages_slug", "pages", ["slug"])

    if "pages_tags" not in tables:
        op.create_table(
            "pages_tags",
            sa.Column(
                "page_id",
                sa.Integer(),
                sa.ForeignKey("pages.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "tag_id",
                sa.Integer(),
                sa.ForeignKey("tags.id", ondelete="CASCADE"),
                primary_key=True,
            ),
        )

    # ------------------------------------------------------------------
    # Migrate legacy research / notebooks data into pages.
    # ------------------------------------------------------------------
    if {"research", "notebooks"}.issubset(tables):
        _convert_legacy(bind)

    # Drop legacy tables now that data is moved.
    tables = set(sa.inspect(bind).get_table_names())
    for legacy in ("research_tags", "notebooks", "research"):
        if legacy in tables:
            op.drop_table(legacy)
            tables.discard(legacy)

    # ------------------------------------------------------------------
    # Comments / reactions: ensure they reference page_id.
    # ------------------------------------------------------------------
    if "comments" not in tables:
        op.create_table(
            "comments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "page_id",
                sa.Integer(),
                sa.ForeignKey("pages.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "author_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_comments_id", "comments", ["id"])
        op.create_index("ix_comments_page_id", "comments", ["page_id"])
    else:
        cols = {col["name"] for col in sa.inspect(bind).get_columns("comments")}
        if "research_id" in cols and "page_id" not in cols:
            op.add_column("comments", sa.Column("page_id", sa.Integer(), nullable=True))
            bind.execute(sa.text("UPDATE comments SET page_id = research_id"))
            _drop_fkeys_referencing(bind, "comments", "research_id")
            op.drop_index("ix_comments_research_id", table_name="comments", if_exists=True)
            op.drop_column("comments", "research_id")
            op.alter_column("comments", "page_id", nullable=False)
            op.create_foreign_key(
                "comments_page_id_fkey",
                "comments",
                "pages",
                ["page_id"],
                ["id"],
                ondelete="CASCADE",
            )
            op.create_index("ix_comments_page_id", "comments", ["page_id"])

    if "reactions" not in tables:
        op.create_table(
            "reactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "page_id",
                sa.Integer(),
                sa.ForeignKey("pages.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("emoji", sa.String(length=10), nullable=False, server_default="👍"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("page_id", "user_id", name="uq_reaction_user_page"),
        )
        op.create_index("ix_reactions_id", "reactions", ["id"])
        op.create_index("ix_reactions_page_id", "reactions", ["page_id"])
    else:
        cols = {col["name"] for col in sa.inspect(bind).get_columns("reactions")}
        if "research_id" in cols and "page_id" not in cols:
            op.add_column("reactions", sa.Column("page_id", sa.Integer(), nullable=True))
            bind.execute(sa.text("UPDATE reactions SET page_id = research_id"))
            _drop_fkeys_referencing(bind, "reactions", "research_id")
            op.drop_constraint("uq_reaction_user_research", "reactions", type_="unique")
            op.drop_index("ix_reactions_research_id", table_name="reactions", if_exists=True)
            op.drop_column("reactions", "research_id")
            op.alter_column("reactions", "page_id", nullable=False)
            op.create_foreign_key(
                "reactions_page_id_fkey",
                "reactions",
                "pages",
                ["page_id"],
                ["id"],
                ondelete="CASCADE",
            )
            op.create_unique_constraint("uq_reaction_user_page", "reactions", ["page_id", "user_id"])
            op.create_index("ix_reactions_page_id", "reactions", ["page_id"])


def downgrade() -> None:
    # This redesign is one-way; downgrading would need to materialise notebooks
    # back from the markdown source which is not implemented.
    raise NotImplementedError("Cannot downgrade past the pages redesign.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _convert_legacy(bind: sa.engine.Connection) -> None:
    """Copy `research` + first notebook into `pages` (with extended markdown)."""
    from app.services.extended_md import from_nbformat

    rows = bind.execute(
        sa.text(
            """
            SELECT r.id, r.slug, r.title, r.description, r.author_id,
                   r.is_interactive, r.published_at, r.updated_at,
                   (
                     SELECT n.content FROM notebooks n
                     WHERE n.research_id = r.id
                     ORDER BY n."order" ASC
                     LIMIT 1
                   ) AS content
            FROM research r
            """
        )
    ).fetchall()

    for row in rows:
        notebook_content = row.content
        if isinstance(notebook_content, (bytes, bytearray)):
            import json as _json
            try:
                notebook_content = _json.loads(notebook_content)
            except Exception:
                notebook_content = None
        try:
            source_md = from_nbformat(notebook_content) if notebook_content else ""
        except Exception:
            source_md = ""

        bind.execute(
            sa.text(
                """
                INSERT INTO pages (id, slug, title, description, author_id,
                                   is_interactive, source_md, is_draft,
                                   published_at, updated_at)
                VALUES (:id, :slug, :title, :description, :author_id,
                        :is_interactive, :source_md, false,
                        :published_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": row.id,
                "slug": row.slug,
                "title": row.title,
                "description": row.description,
                "author_id": row.author_id,
                "is_interactive": row.is_interactive,
                "source_md": source_md,
                "published_at": row.published_at,
                "updated_at": row.updated_at,
            },
        )

    # Realign the pages id sequence so future inserts don't collide.
    bind.execute(
        sa.text(
            "SELECT setval('pages_id_seq', GREATEST(COALESCE((SELECT MAX(id) FROM pages), 0), 1))"
        )
    )

    # Copy tag links.
    bind.execute(
        sa.text(
            """
            INSERT INTO pages_tags (page_id, tag_id)
            SELECT research_id, tag_id FROM research_tags
            ON CONFLICT DO NOTHING
            """
        )
    )


def _drop_fkeys_referencing(bind: sa.engine.Connection, table: str, column: str) -> None:
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table):
        if column in fk.get("constrained_columns", []):
            name = fk.get("name")
            if name:
                op.drop_constraint(name, table, type_="foreignkey")

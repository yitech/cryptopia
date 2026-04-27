"""One-shot migration: convert legacy research+notebooks rows into pages,
repoint comments/reactions to pages, and drop the legacy tables.

Idempotent: skips the work cleanly if the DB is already on the new schema.
Run inside the backend container:

    docker exec cryptopia-backend-1 python -m scripts.migrate_legacy_to_pages
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.database import engine
from app.services import extended_md


def _slugify(value: str) -> str:
    s = (value or "untitled").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "untitled"


async def _column_exists(conn, table: str, column: str) -> bool:
    row = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
        ),
        {"t": table, "c": column},
    )
    return row.scalar() is not None


async def _table_exists(conn, table: str) -> bool:
    row = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=:t"
        ),
        {"t": table},
    )
    return row.scalar() is not None


async def main() -> None:
    async with engine.begin() as conn:
        legacy_research = await _table_exists(conn, "research")
        legacy_notebooks = await _table_exists(conn, "notebooks")

        # ------------------------------------------------------------------
        # 1. Convert each legacy research row into a page row (if any).
        # ------------------------------------------------------------------
        research_to_page: dict[int, int] = {}
        if legacy_research:
            rows = await conn.execute(
                text(
                    "SELECT r.id, r.slug, r.title, r.description, r.author_id, "
                    "       r.published_at, r.updated_at, "
                    "       n.content "
                    "FROM research r "
                    "LEFT JOIN notebooks n ON n.research_id = r.id"
                )
            )
            for r in rows.mappings():
                source_md: str
                content = r["content"]
                if content:
                    if isinstance(content, str):
                        try:
                            content = json.loads(content)
                        except Exception:
                            content = None
                    if isinstance(content, dict):
                        source_md = extended_md.from_nbformat(content)
                    else:
                        source_md = ""
                else:
                    source_md = ""

                meta = extended_md.derive_metadata(source_md)
                title = r["title"] or meta["title"] or "Untitled"
                description = r["description"] or meta["description"]
                slug = r["slug"] or _slugify(title)
                # Legacy `research` rows had no draft flag — they were always public.
                is_draft = False
                now = datetime.now(timezone.utc)

                page_row = await conn.execute(
                    text(
                        "INSERT INTO pages "
                        "(slug, title, description, author_id, is_interactive, "
                        " source_md, is_draft, published_at, updated_at) "
                        "VALUES (:slug, :title, :description, :author_id, "
                        "        :is_interactive, :source_md, :is_draft, "
                        "        :published_at, :updated_at) "
                        "RETURNING id"
                    ),
                    {
                        "slug": slug,
                        "title": title,
                        "description": description,
                        "author_id": r["author_id"],
                        "is_interactive": meta["is_interactive"],
                        "source_md": source_md,
                        "is_draft": is_draft,
                        "published_at": r["published_at"] or now,
                        "updated_at": r["updated_at"] or now,
                    },
                )
                page_id = page_row.scalar_one()
                research_to_page[int(r["id"])] = int(page_id)
                print(f"[migrate] research#{r['id']} -> page#{page_id} ({title!r})")

            # Carry over research_tags → pages_tags via the id remap.
            if research_to_page and await _table_exists(conn, "research_tags"):
                rt_rows = await conn.execute(
                    text("SELECT research_id, tag_id FROM research_tags")
                )
                for rt in rt_rows.mappings():
                    page_id = research_to_page.get(int(rt["research_id"]))
                    if page_id is None:
                        continue
                    await conn.execute(
                        text(
                            "INSERT INTO pages_tags (page_id, tag_id) "
                            "VALUES (:p, :t) ON CONFLICT DO NOTHING"
                        ),
                        {"p": page_id, "t": rt["tag_id"]},
                    )

        # ------------------------------------------------------------------
        # 2. Rename comments.research_id -> page_id (FK to pages).
        # ------------------------------------------------------------------
        if await _column_exists(conn, "comments", "research_id"):
            # Both are empty in the affected DB, but be safe and remap any rows.
            if research_to_page:
                for old_id, new_id in research_to_page.items():
                    await conn.execute(
                        text(
                            "UPDATE comments SET research_id=:n WHERE research_id=:o"
                        ),
                        {"o": old_id, "n": new_id},
                    )
            await conn.execute(text("ALTER TABLE comments DROP CONSTRAINT IF EXISTS comments_research_id_fkey"))
            await conn.execute(text("DROP INDEX IF EXISTS ix_comments_research_id"))
            await conn.execute(text("ALTER TABLE comments RENAME COLUMN research_id TO page_id"))
            await conn.execute(
                text(
                    "ALTER TABLE comments ADD CONSTRAINT comments_page_id_fkey "
                    "FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE"
                )
            )
            await conn.execute(text("CREATE INDEX ix_comments_page_id ON comments (page_id)"))
            print("[migrate] comments.research_id -> page_id")

        # ------------------------------------------------------------------
        # 3. Same for reactions, plus the unique constraint rename.
        # ------------------------------------------------------------------
        if await _column_exists(conn, "reactions", "research_id"):
            if research_to_page:
                for old_id, new_id in research_to_page.items():
                    await conn.execute(
                        text(
                            "UPDATE reactions SET research_id=:n WHERE research_id=:o"
                        ),
                        {"o": old_id, "n": new_id},
                    )
            await conn.execute(text("ALTER TABLE reactions DROP CONSTRAINT IF EXISTS reactions_research_id_fkey"))
            await conn.execute(text("ALTER TABLE reactions DROP CONSTRAINT IF EXISTS uq_reaction_user_research"))
            await conn.execute(text("DROP INDEX IF EXISTS ix_reactions_research_id"))
            await conn.execute(text("ALTER TABLE reactions RENAME COLUMN research_id TO page_id"))
            await conn.execute(
                text(
                    "ALTER TABLE reactions ADD CONSTRAINT reactions_page_id_fkey "
                    "FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE reactions ADD CONSTRAINT uq_reaction_user_page "
                    "UNIQUE (page_id, user_id)"
                )
            )
            await conn.execute(text("CREATE INDEX ix_reactions_page_id ON reactions (page_id)"))
            print("[migrate] reactions.research_id -> page_id")

        # ------------------------------------------------------------------
        # 4. Drop legacy tables (children first so FKs can dissolve cleanly).
        # ------------------------------------------------------------------
        for legacy in ("research_tags", "notebooks", "research"):
            if await _table_exists(conn, legacy):
                await conn.execute(text(f"DROP TABLE {legacy} CASCADE"))
                print(f"[migrate] dropped legacy table {legacy}")

    print("[migrate] done")


if __name__ == "__main__":
    asyncio.run(main())

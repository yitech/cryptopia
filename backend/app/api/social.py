from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user, get_current_user_optional
from app.models.user import User
from app.models.page import Page
from app.models.social import Comment, Reaction

router = APIRouter(prefix="/api/social", tags=["social"])

ALLOWED_EMOJIS = {"👍", "❤️", "🔥", "🎉", "🤔", "💡"}


class CommentCreate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    id: int
    content: str
    author_username: str
    author_full_name: str | None
    created_at: str

    model_config = {"from_attributes": True}


@router.get("/pages/{page_id}/comments")
async def list_comments(page_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.page_id == page_id)
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()
    return [
        {
            "id": c.id,
            "content": c.content,
            "author_username": c.author.username,
            "author_full_name": c.author.full_name,
            "created_at": c.created_at.isoformat(),
        }
        for c in comments
    ]


@router.post("/pages/{page_id}/comments", status_code=201)
async def create_comment(
    page_id: int,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = payload.content.strip()
    if not content or len(content) > 2000:
        raise HTTPException(400, "Comment must be 1–2000 characters")

    result = await db.execute(select(Page).where(Page.id == page_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Page not found")

    comment = Comment(page_id=page_id, author_id=current_user.id, content=content)
    db.add(comment)
    await db.flush()
    await db.refresh(comment)

    return {
        "id": comment.id,
        "content": comment.content,
        "author_username": current_user.username,
        "author_full_name": current_user.full_name,
        "created_at": comment.created_at.isoformat(),
    }


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(404, "Comment not found")
    if comment.author_id != current_user.id:
        raise HTTPException(403, "Not allowed")
    await db.delete(comment)


@router.get("/pages/{page_id}/reactions")
async def get_reactions(
    page_id: int,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reaction.emoji, func.count(Reaction.id).label("count"))
        .where(Reaction.page_id == page_id)
        .group_by(Reaction.emoji)
    )
    counts = {row.emoji: row.count for row in result.all()}

    my_reaction = None
    if current_user:
        r = await db.execute(
            select(Reaction).where(
                Reaction.page_id == page_id,
                Reaction.user_id == current_user.id,
            )
        )
        rx = r.scalar_one_or_none()
        if rx:
            my_reaction = rx.emoji

    return {"counts": counts, "my_reaction": my_reaction}


@router.post("/pages/{page_id}/reactions")
async def toggle_reaction(
    page_id: int,
    emoji: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if emoji not in ALLOWED_EMOJIS:
        raise HTTPException(400, f"Emoji must be one of: {', '.join(ALLOWED_EMOJIS)}")

    result = await db.execute(select(Page).where(Page.id == page_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Page not found")

    existing = await db.execute(
        select(Reaction).where(
            Reaction.page_id == page_id,
            Reaction.user_id == current_user.id,
        )
    )
    rx = existing.scalar_one_or_none()

    if rx:
        if rx.emoji == emoji:
            await db.delete(rx)
        else:
            rx.emoji = emoji
    else:
        rx = Reaction(page_id=page_id, user_id=current_user.id, emoji=emoji)
        db.add(rx)

    return {"ok": True}

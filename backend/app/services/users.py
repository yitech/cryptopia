"""Upsert + lookup helpers for the locally-mirrored User table."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthIdentity
from app.models.user import User


async def upsert_from_identity(session: AsyncSession, identity: AuthIdentity) -> User:
    """Insert or refresh a :class:`User` row from an Authelia identity."""
    stmt = select(User).where(User.username == identity.username)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is None:
        user = User(
            username=identity.username,
            email=identity.email,
            display_name=identity.name or identity.username,
        )
        session.add(user)
        await session.flush()
        return user

    changed = False
    if identity.email and user.email != identity.email:
        user.email = identity.email
        changed = True
    if identity.name and user.display_name != identity.name:
        user.display_name = identity.name
        changed = True
    user.last_seen_at = datetime.now(UTC)
    if changed:
        await session.flush()
    return user


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)

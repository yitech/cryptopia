"""Schema for ``GET /api/me``."""

from __future__ import annotations

from pydantic import BaseModel


class MeResponse(BaseModel):
    authenticated: bool
    username: str | None = None
    email: str | None = None
    name: str | None = None
    groups: list[str] = []
    authelia_url: str

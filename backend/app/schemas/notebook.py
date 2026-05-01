"""Request / response models for the notebook API."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.notebook import Visibility

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,118}[a-z0-9])?$")


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    display_name: str


class NotebookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str | None = None
    description: str = ""
    visibility: Visibility = Visibility.TEAM
    allowed_groups: list[str] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not _SLUG_RE.match(v):
            raise ValueError(
                "slug must be lowercase alphanumerics + dashes (1-120 chars), "
                "and cannot start or end with a dash",
            )
        return v


class NotebookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    visibility: Visibility | None = None
    allowed_groups: list[str] | None = None


class NotebookSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str
    description: str
    visibility: Visibility
    allowed_groups: list[str]
    owner: UserPublic
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    published_version: int | None


class NotebookDetail(NotebookSummary):
    can_edit: bool = False
    can_run: bool = False
    is_published: bool = False


class NotebookVersionInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    content_hash: str
    published_at: datetime
    published_by: int


class PublishResponse(BaseModel):
    notebook_id: str
    version: int
    published_at: datetime
    static_url: str | None = None
    run_url: str

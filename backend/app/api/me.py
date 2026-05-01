"""``/api/me`` route — exposes the current Authelia identity as JSON."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import AuthIdentity, get_optional_identity
from app.core.config import Settings, get_settings
from app.schemas.me import MeResponse

router = APIRouter()


@router.get("/me", response_model=MeResponse)
async def get_me(
    identity: AuthIdentity | None = Depends(get_optional_identity),
    settings: Settings = Depends(get_settings),
) -> MeResponse:
    if identity is None:
        return MeResponse(authenticated=False, authelia_url=settings.authelia_url)
    return MeResponse(
        authenticated=True,
        username=identity.username,
        email=identity.email or None,
        name=identity.name or None,
        groups=list(identity.groups),
        authelia_url=settings.authelia_url,
    )

"""Authelia forward-auth integration.

Cryptopia trusts the reverse proxy (Caddy/Traefik/nginx) sitting in front of
it to do the real Authelia handshake and to inject the verified identity as
HTTP headers (``Remote-User``, ``Remote-Email``, ``Remote-Name``,
``Remote-Groups``). This module turns those headers into a typed
:class:`AuthIdentity` and exposes a FastAPI dependency for routes.

For local development without the proxy chain, set ``CRYPTOPIA_DEV_AUTH_USER``
in the environment to fake an authenticated user.

We deliberately avoid talking to Authelia ourselves: the proxy already does
that on every request, so doing it again would only burn latency and
introduce another moving piece.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class AuthIdentity:
    username: str
    email: str = ""
    name: str = ""
    groups: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.username)

    def in_any_group(self, groups: list[str] | tuple[str, ...]) -> bool:
        if not groups:
            return False
        return any(g in self.groups for g in groups)


def _split_groups(raw: str) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(g.strip() for g in raw.split(",") if g.strip())


def extract_identity(request: Request, settings: Settings | None = None) -> AuthIdentity | None:
    """Pull the Authelia identity out of trusted forward-auth headers.

    Returns ``None`` if the request is anonymous (no auth headers and no
    dev bypass configured).
    """
    settings = settings or get_settings()
    headers = request.headers

    username = headers.get(settings.auth_header_user, "").strip()
    if not username and settings.dev_auth_user:
        return AuthIdentity(
            username=settings.dev_auth_user,
            email=settings.dev_auth_email,
            name=settings.dev_auth_name or settings.dev_auth_user,
            groups=_split_groups(settings.dev_auth_groups),
        )
    if not username:
        return None

    return AuthIdentity(
        username=username,
        email=headers.get(settings.auth_header_email, "").strip(),
        name=headers.get(settings.auth_header_name, "").strip() or username,
        groups=_split_groups(headers.get(settings.auth_header_groups, "")),
    )


def get_optional_identity(request: Request) -> AuthIdentity | None:
    """FastAPI dependency: identity if logged in, otherwise ``None``."""
    return extract_identity(request)


def require_identity(request: Request) -> AuthIdentity:
    """FastAPI dependency: 401 if no Authelia identity is present."""
    ident = extract_identity(request)
    if ident is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Forward-Auth"},
        )
    return ident


__all__ = [
    "AuthIdentity",
    "extract_identity",
    "get_optional_identity",
    "require_identity",
]

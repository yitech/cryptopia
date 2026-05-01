"""Reverse proxy that wraps the per-notebook ``marimo edit`` subprocess.

Mounted at ``/api/edit/<notebook_id>/...``. We do two jobs:

  1. Authentication — every byte that leaves Cryptopia for the upstream
     subprocess passes ``require_identity`` and an owner check first.
  2. Tunneling — bidirectional HTTP and WebSocket relay to ``127.0.0.1`` on
     the subprocess's port.

We deliberately keep the path *unchanged* when forwarding because we start
``marimo edit`` with ``--base-url /api/edit/<id>`` so its own asset URLs
already include the prefix.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import typing

import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from app.core.auth import (
    AuthIdentity,
    extract_identity,
    require_identity,
)
from app.db.base import SessionLocal, get_session
from app.services import notebooks as nb_service
from app.services.edit_sessions import EditSession, edit_session_manager

LOG = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# HTTP


# httpx Client kept process-wide; created lazily on first use so the import
# graph stays cheap during cold start.
_http_client: httpx.AsyncClient | None = None


async def _client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=None), follow_redirects=False)
    return _http_client


async def shutdown_http_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
        "content-encoding",
    }
)


def _filter_request_headers(req: Request) -> dict[str, str]:
    return {
        name: value
        for name, value in req.headers.items()
        if name.lower() not in _HOP_BY_HOP
    }


def _filter_response_headers(headers: httpx.Headers) -> list[tuple[str, str]]:
    return [
        (name, value)
        for name, value in headers.multi_items()
        if name.lower() not in _HOP_BY_HOP
    ]


async def _ensure_session_for(notebook_id: str, identity: AuthIdentity) -> EditSession:
    async with SessionLocal() as session:
        nb = await nb_service.get_by_id(session, notebook_id)
        if nb is None:
            raise HTTPException(status_code=404, detail="Notebook not found")
        if not nb_service.can_edit(nb, identity):
            raise HTTPException(status_code=403, detail="Only the owner can edit this notebook")
        path = nb_service.working_file_path(nb)
    try:
        return await edit_session_manager.get_or_start(notebook_id, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.api_route(
    "/edit/{notebook_id}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
@router.api_route(
    "/edit/{notebook_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def proxy_edit(
    notebook_id: str,
    request: Request,
    path: str = "",
    identity: AuthIdentity = Depends(require_identity),
    _session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    edit_session = await _ensure_session_for(notebook_id, identity)
    edit_session.touch()

    # Marimo was launched with --base-url /api/edit/<id>, so it expects to
    # see that prefix on its own requests. We rebuild the upstream URL by
    # taking the original path (which already includes the prefix) and
    # forwarding it verbatim.
    upstream_path = request.url.path
    query = request.url.query
    upstream_url = edit_session.upstream_base + upstream_path + (f"?{query}" if query else "")

    body = await request.body()
    client = await _client()

    upstream_request = client.build_request(
        request.method,
        upstream_url,
        content=body,
        headers=_filter_request_headers(request),
    )
    try:
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.RequestError as exc:
        LOG.warning("Edit proxy upstream error for %s: %s", notebook_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Edit session is not reachable",
        ) from exc

    async def _stream() -> typing.AsyncIterator[bytes]:
        try:
            async for chunk in upstream_response.aiter_raw():
                yield chunk
        finally:
            await upstream_response.aclose()

    return StreamingResponse(
        _stream(),
        status_code=upstream_response.status_code,
        headers=dict(_filter_response_headers(upstream_response.headers)),
    )


# ---------------------------------------------------------------------------
# WebSocket


@router.websocket("/edit/{notebook_id}/ws")
@router.websocket("/edit/{notebook_id}/ws/{path:path}")
async def proxy_edit_ws(
    websocket: WebSocket,
    notebook_id: str,
    path: str = "",
) -> None:
    """Relay marimo's editor WebSocket through Cryptopia.

    Authelia headers come in on the initial WS handshake just like an HTTP
    request, so we run :func:`extract_identity` directly instead of using
    a FastAPI dependency (which requires an HTTP request scope).
    """
    identity = extract_identity(websocket)  # type: ignore[arg-type]
    if identity is None:
        await websocket.close(code=4401)
        return

    try:
        edit_session = await _ensure_session_for(notebook_id, identity)
    except HTTPException as exc:
        # 4xxx codes are application-defined per RFC 6455.
        code = 4000 + (exc.status_code or 500) % 1000
        await websocket.close(code=code, reason=str(exc.detail)[:120])
        return
    edit_session.touch()

    await websocket.accept(subprotocol=websocket.headers.get("sec-websocket-protocol"))

    upstream_path = websocket.url.path
    query = websocket.url.query
    upstream_url = edit_session.upstream_ws_base + upstream_path + (f"?{query}" if query else "")

    try:
        async with ws_connect(
            upstream_url,
            additional_headers=_ws_forward_headers(websocket),
            max_size=None,
            open_timeout=10,
            ping_interval=None,
        ) as upstream:
            await asyncio.gather(
                _pump_client_to_upstream(websocket, upstream, edit_session),
                _pump_upstream_to_client(websocket, upstream, edit_session),
            )
    except (WebSocketDisconnect, ConnectionClosed):
        pass
    except Exception:
        LOG.exception("Edit WS proxy crashed for %s", notebook_id)
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            with contextlib.suppress(Exception):
                await websocket.close()


def _ws_forward_headers(ws: WebSocket) -> list[tuple[str, str]]:
    skip = {
        "host",
        "connection",
        "upgrade",
        "sec-websocket-key",
        "sec-websocket-version",
        "sec-websocket-extensions",
        "sec-websocket-accept",
        "sec-websocket-protocol",
    }
    return [
        (name, value)
        for name, value in ws.headers.items()
        if name.lower() not in skip
    ]


async def _pump_client_to_upstream(
    client_ws: WebSocket,
    upstream: ClientConnection,
    edit_session: EditSession,
) -> None:
    while True:
        msg = await client_ws.receive()
        if msg["type"] == "websocket.disconnect":
            await upstream.close()
            return
        edit_session.touch()
        if "text" in msg and msg["text"] is not None:
            await upstream.send(msg["text"])
        elif "bytes" in msg and msg["bytes"] is not None:
            await upstream.send(msg["bytes"])


async def _pump_upstream_to_client(
    client_ws: WebSocket,
    upstream: ClientConnection,
    edit_session: EditSession,
) -> None:
    async for message in upstream:
        edit_session.touch()
        if isinstance(message, str):
            await client_ws.send_text(message)
        else:
            await client_ws.send_bytes(message)



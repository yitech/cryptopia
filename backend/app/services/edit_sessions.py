"""Per-notebook ``marimo edit`` subprocess manager.

Each notebook that's being edited gets its own ``marimo edit`` process bound
to ``127.0.0.1`` on an ephemeral port. Cryptopia proxies the editor's HTTP
and WebSocket traffic through ``/api/edit/<id>/...``, gating it on:

  1. Authelia forward-auth must be present (anonymous users get 401).
  2. The requester must be the notebook's owner.

We pass ``--no-token`` to marimo because every byte going to the subprocess
already passed our auth gate. The subprocess itself only listens on
loopback, so it isn't reachable from outside the container.

A session is started lazily on the first proxied request (kept track of in
``EditSessionManager``) and shut down when:

  * the FastAPI app shuts down,
  * the notebook is deleted, or
  * the session has been idle for ``CRYPTOPIA_EDIT_IDLE_TIMEOUT`` seconds.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings, get_settings

LOG = logging.getLogger(__name__)


def _pick_free_port(start: int, end: int) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free port available in {start}-{end}")


@dataclass
class EditSession:
    notebook_id: str
    file_path: Path
    base_path: str
    port: int
    process: asyncio.subprocess.Process
    last_active: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.last_active = time.monotonic()

    @property
    def upstream_base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def upstream_ws_base(self) -> str:
        return f"ws://127.0.0.1:{self.port}"


class EditSessionManager:
    """Owns the lifecycle of every running ``marimo edit`` subprocess."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._sessions: dict[str, EditSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._reaper_task: asyncio.Task[None] | None = None

    # -- lifecycle -----------------------------------------------------------

    async def startup(self) -> None:
        if self._reaper_task is None:
            self._reaper_task = asyncio.create_task(self._reaper_loop())

    async def shutdown(self) -> None:
        if self._reaper_task is not None:
            self._reaper_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reaper_task
            self._reaper_task = None
        for session in list(self._sessions.values()):
            await self._kill(session)
        self._sessions.clear()

    # -- public API ----------------------------------------------------------

    async def get_or_start(self, notebook_id: str, file_path: Path) -> EditSession:
        """Return the running session for ``notebook_id``, starting one if needed.

        The first request to a freshly-created session pays the cost of
        actually launching the subprocess; subsequent requests just return
        the cached session and bump its last-active timestamp.
        """
        existing = self._sessions.get(notebook_id)
        if existing is not None and existing.process.returncode is None:
            existing.touch()
            return existing

        lock = self._locks.setdefault(notebook_id, asyncio.Lock())
        async with lock:
            existing = self._sessions.get(notebook_id)
            if existing is not None and existing.process.returncode is None:
                existing.touch()
                return existing
            session = await self._start(notebook_id, file_path)
            self._sessions[notebook_id] = session
            return session

    async def stop(self, notebook_id: str) -> None:
        session = self._sessions.pop(notebook_id, None)
        if session is not None:
            await self._kill(session)

    # -- internals -----------------------------------------------------------

    async def _start(self, notebook_id: str, file_path: Path) -> EditSession:
        if not file_path.exists():
            raise FileNotFoundError(f"Working file missing: {file_path}")

        # Resolve once so the subprocess (which we spawn with a different
        # cwd) doesn't accidentally re-interpret a relative path.
        file_path = file_path.resolve()

        port = _pick_free_port(
            self._settings.edit_port_range_start, self._settings.edit_port_range_end
        )
        base_path = f"/api/edit/{notebook_id}"

        cmd = [
            sys.executable,
            "-m",
            "marimo",
            "edit",
            str(file_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-token",
            "--headless",
            "--skip-update-check",
            "--base-url",
            base_path,
            "--allow-origins",
            "*",
        ]
        LOG.info("Starting edit session %s: port=%d file=%s", notebook_id, port, file_path)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(file_path.parent),
        )

        # Wait until the upstream is accepting connections, but bound the
        # wait so we never deadlock the request that triggered the start.
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if proc.returncode is not None:
                stderr = await proc.stderr.read() if proc.stderr else b""
                raise RuntimeError(
                    f"marimo edit exited early (rc={proc.returncode}): "
                    f"{stderr.decode('utf-8', 'replace')[:500]}"
                )
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                await asyncio.sleep(0.2)
        else:
            await self._terminate_process(proc)
            raise RuntimeError("marimo edit did not start in time")

        return EditSession(
            notebook_id=notebook_id,
            file_path=file_path,
            base_path=base_path,
            port=port,
            process=proc,
        )

    async def _kill(self, session: EditSession) -> None:
        await self._terminate_process(session.process)

    @staticmethod
    async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is not None:
            return
        try:
            proc.terminate()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(Exception):
                await proc.wait()

    async def _reaper_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(60)
                idle_limit = self._settings.edit_idle_timeout
                now = time.monotonic()
                stale: list[str] = []
                for nb_id, session in self._sessions.items():
                    if session.process.returncode is not None:
                        stale.append(nb_id)
                        continue
                    if now - session.last_active > idle_limit:
                        stale.append(nb_id)
                for nb_id in stale:
                    LOG.info("Reaping idle edit session %s", nb_id)
                    await self.stop(nb_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("edit-session reaper crashed; restarting loop")


# A module-level instance keeps things simple. FastAPI lifecycle wires
# ``startup`` / ``shutdown`` to it.
edit_session_manager = EditSessionManager()


__all__ = ["EditSession", "EditSessionManager", "edit_session_manager"]

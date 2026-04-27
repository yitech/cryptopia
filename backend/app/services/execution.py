"""
Kernel pool and request-scoped page execution.

A kernel is keyed per page. Code cells are sourced from the page's extended
markdown via `extract_code_cells`. The cryptopia SDK emits widget specs over
stdout with the `CRYPTOPIA_WIDGET:` prefix; this module captures them and
returns them to the API layer.

Two operations are exposed:

- `run_single_cell` — execute one code cell against the kernel and return
  its complete output list. Used both by the editor's Run button and by
  viewers running a published page.
- `dispatch_widget`  — invoke the SDK callback registered for a widget id
  (set up during a previous cell run) and return the outputs the callback
  produced. This is the only path used at runtime once the page has been
  initialized — the frontend never opens a long-lived connection.
"""
import asyncio
import base64
import json
import time
from typing import Iterable

import jupyter_client

from app.services.extended_md import CodeCell, extract_code_cells


WIDGET_PREFIX = "CRYPTOPIA_WIDGET:"


class KernelEntry:
    def __init__(self, km: jupyter_client.AsyncKernelManager, kc: jupyter_client.AsyncKernelClient):
        self.km = km
        self.kc = kc
        self.last_used = time.monotonic()
        self.lock = asyncio.Lock()


class KernelPool:
    """
    Kernel pool keyed by page_id. Kernels are evicted after `ttl` seconds of
    inactivity, or when the pool is at `max_kernels` and a new page asks for
    its own kernel.
    """

    def __init__(self, ttl: int = 600, max_kernels: int = 20):
        self._pool: dict[int, KernelEntry] = {}
        self._ttl = ttl
        self._max = max_kernels
        self._lock = asyncio.Lock()

    async def get_or_create(self, page_id: int, kernel_name: str = "python3") -> KernelEntry:
        async with self._lock:
            entry = self._pool.get(page_id)
            if entry and await self._is_alive(entry):
                entry.last_used = time.monotonic()
                return entry

            if entry:
                await self._shutdown_entry(entry)
                del self._pool[page_id]

            if len(self._pool) >= self._max:
                oldest_key = min(self._pool, key=lambda k: self._pool[k].last_used)
                await self._shutdown_entry(self._pool[oldest_key])
                del self._pool[oldest_key]

            km = jupyter_client.AsyncKernelManager(kernel_name=kernel_name)
            await km.start_kernel()
            kc = km.client()
            kc.start_channels()
            await kc.wait_for_ready(timeout=30)

            entry = KernelEntry(km, kc)
            self._pool[page_id] = entry
            return entry

    async def reset(self, page_id: int) -> None:
        """Forcibly shutdown the kernel for a page (e.g. after edits)."""
        async with self._lock:
            entry = self._pool.pop(page_id, None)
            if entry:
                await self._shutdown_entry(entry)

    async def _is_alive(self, entry: KernelEntry) -> bool:
        try:
            return await entry.km.is_alive()
        except Exception:
            return False

    async def _shutdown_entry(self, entry: KernelEntry):
        try:
            entry.kc.stop_channels()
            await entry.km.shutdown_kernel(now=True)
        except Exception:
            pass

    async def evict_idle(self):
        async with self._lock:
            now = time.monotonic()
            stale = [k for k, v in self._pool.items() if now - v.last_used > self._ttl]
            for k in stale:
                await self._shutdown_entry(self._pool[k])
                del self._pool[k]

    async def shutdown_all(self):
        async with self._lock:
            for entry in self._pool.values():
                await self._shutdown_entry(entry)
            self._pool.clear()


kernel_pool = KernelPool()


# ---------------------------------------------------------------------------
# Page execution
# ---------------------------------------------------------------------------

async def run_single_cell(
    *,
    page_id: int,
    source_md: str,
    cell_id: str,
    widget_values: dict | None = None,
    kernel_name: str = "python3",
) -> dict:
    """
    Run one cell against the page's kernel and return
    `{"outputs": [...], "error": str|None}`.

    `widget_values` are injected into `__main__.__cx_widget_values__` before
    the cell runs so SDK calls like `cx.slider(...)` resolve to the latest
    user-supplied values. Used by `POST /api/pages/{id}/run-cell` for both
    the editor and the viewer.
    """
    cells = extract_code_cells(source_md)
    target = next((c for c in cells if c.id == cell_id), None)
    if target is None:
        return {"outputs": [], "error": f"Cell {cell_id!r} not found"}

    entry = await kernel_pool.get_or_create(page_id, kernel_name)
    async with entry.lock:
        entry.last_used = time.monotonic()
        kc = entry.kc

        await _inject_widget_values(kc, widget_values or {})
        outputs = await _run_cell_collect(kc, target)
        return {"outputs": outputs, "error": _first_error(outputs)}


async def dispatch_widget(
    *,
    page_id: int,
    widget_id: str,
    value,
    kernel_name: str = "python3",
) -> dict:
    """
    Invoke the SDK on_change callback registered for `widget_id` against the
    page's kernel.

    The kernel exposes `__cx_dispatch__(widget_id, value)` (defined by the
    cryptopia SDK at import time). Calling it looks up the registered
    callback, runs it, and re-emits any widgets / display data it produced.
    We capture and return those as a normal output list.

    Returns `{"outputs": [...], "error": str|None}`. If the widget has no
    registered callback the SDK helper is expected to be a no-op and the
    output list will be empty.
    """
    entry = await kernel_pool.get_or_create(page_id, kernel_name)
    async with entry.lock:
        entry.last_used = time.monotonic()
        kc = entry.kc

        payload = json.dumps({"widget_id": widget_id, "value": value})
        src = (
            "import json as __cx_json__\n"
            "import cryptopia as __cx__\n"
            f"__cx_payload__ = __cx_json__.loads({payload!r})\n"
            "__cx__._dispatch(__cx_payload__['widget_id'], __cx_payload__['value'])\n"
        )
        msg_id = kc.execute(src)
        outputs = await _collect_outputs(kc, msg_id)
        return {"outputs": outputs, "error": _first_error(outputs)}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

async def _inject_widget_values(kc: jupyter_client.AsyncKernelClient, widget_values: dict) -> None:
    inject = (
        f"__cx_widget_values__ = {json.dumps(widget_values)}\n"
        "import sys as __cx_sys__\n"
    )
    msg_id = kc.execute(inject, silent=True)
    await _drain_until_idle(kc, msg_id)


async def _run_cell_collect(
    kc: jupyter_client.AsyncKernelClient,
    cell: CodeCell,
) -> list[dict]:
    """Execute a cell and return Cryptopia output records."""
    src = cell.source
    if not src.strip():
        return []
    msg_id = kc.execute(src)
    return await _collect_outputs(kc, msg_id)


async def _drain_until_idle(kc: jupyter_client.AsyncKernelClient, msg_id: str) -> None:
    while True:
        try:
            msg = await asyncio.wait_for(kc.get_iopub_msg(), timeout=10.0)
            if msg["parent_header"].get("msg_id") != msg_id:
                continue
            if msg["msg_type"] == "status" and msg["content"]["execution_state"] == "idle":
                break
        except asyncio.TimeoutError:
            break


async def _collect_outputs(
    kc: jupyter_client.AsyncKernelClient,
    msg_id: str,
) -> list[dict]:
    records: list[dict] = []
    while True:
        try:
            msg = await asyncio.wait_for(kc.get_iopub_msg(), timeout=60.0)
        except asyncio.TimeoutError:
            records.append({"type": "error", "ename": "TimeoutError",
                            "evalue": "Cell execution timed out", "traceback": []})
            return records

        if msg["parent_header"].get("msg_id") != msg_id:
            continue

        mtype = msg["msg_type"]
        content = msg["content"]

        if mtype == "stream" and content.get("name") == "stdout":
            text: str = content.get("text", "")
            for line in text.splitlines(keepends=False):
                if line.startswith(WIDGET_PREFIX):
                    try:
                        spec = json.loads(line[len(WIDGET_PREFIX):])
                        records.append({"type": "widget", "spec": spec})
                    except Exception:
                        pass
                elif line:
                    records.append({"mime": "text/plain", "data": line + "\n"})
        elif mtype == "stream" and content.get("name") == "stderr":
            records.append({"mime": "text/plain", "data": content.get("text", "")})
        elif mtype in ("display_data", "execute_result"):
            data = content.get("data") or {}
            records.extend(_data_to_records(data))
        elif mtype == "error":
            records.append({
                "type": "error",
                "ename": content.get("ename", ""),
                "evalue": content.get("evalue", ""),
                "traceback": content.get("traceback", []),
            })
        elif mtype == "status" and content.get("execution_state") == "idle":
            return records


def _data_to_records(data: dict) -> Iterable[dict]:
    if "image/png" in data:
        png = data["image/png"]
        if isinstance(png, bytes):
            png = base64.b64encode(png).decode()
        yield {"mime": "image/png", "data": png}
    elif "image/svg+xml" in data:
        yield {"mime": "image/svg+xml", "data": _coerce(data["image/svg+xml"])}
    elif "text/html" in data:
        yield {"mime": "text/html", "data": _coerce(data["text/html"])}
    elif "application/json" in data:
        try:
            yield {"mime": "application/json", "data": json.dumps(data["application/json"])}
        except Exception:
            pass
    elif "text/plain" in data:
        yield {"mime": "text/plain", "data": _coerce(data["text/plain"])}


def _coerce(v) -> str:
    if isinstance(v, list):
        return "".join(v)
    return str(v or "")


def _first_error(records: list[dict]) -> str | None:
    for r in records:
        if r.get("type") == "error":
            ename = r.get("ename", "")
            evalue = r.get("evalue", "")
            tb = r.get("traceback") or []
            tail = "\n".join(tb) if tb else ""
            return f"{ename}: {evalue}\n{tail}".strip()
    return None

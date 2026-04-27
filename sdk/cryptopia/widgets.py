"""
Cryptopia SDK — widget primitives for interactive research notebooks.

Each cx.* call:
  1. Emits a CRYPTOPIA_WIDGET: JSON line to stdout (picked up by the
     execution service)
  2. Reads the resolved value from __cx_widget_values__ (injected by the
     runner before each cell run)
  3. Returns the value so notebook code can use it

When running outside Cryptopia (e.g. locally in Jupyter), fallback defaults
are used and on_change callbacks are simply ignored.

## Reactivity

Input widgets accept an `on_change=` callable that fires when the user
changes the widget on the frontend. The callback is registered in
`__main__.__cx_callbacks__` keyed by widget id. The Cryptopia backend's
`/dispatch` endpoint calls `cryptopia._dispatch(widget_id, value)` against
the persistent kernel; this updates `__cx_widget_values__`, looks up and
invokes the registered callback (if any), and lets it emit fresh widgets /
display data the same way as the original cell run.

A widget can declare *no* callback — that just means "I'm displayed, but
nothing reactive happens when I change". The frontend can still re-run the
owning cell explicitly via the cell's Run button.
"""
import hashlib
import json
import re
from typing import Any, Callable


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text or "").strip("_").lower()
    return s[:32] or "w"


def _widget_id(prefix: str, label: str = "") -> str:
    """
    Build a stable widget id from `prefix` + `label`. Stability across cell
    re-runs is essential — otherwise widget values sent from the frontend
    can never match the freshly emitted widget specs and re-runs would
    silently fall back to defaults. If a notebook genuinely needs two widgets
    with the same prefix+label, callers should pass an explicit `key=` to
    disambiguate.
    """
    digest = hashlib.sha1(f"{prefix}|{label}".encode("utf-8")).hexdigest()[:6]
    return f"{prefix}_{_slug(label)}_{digest}"


def _emit(spec: dict):
    """Write a widget spec to stdout for the execution service to pick up."""
    print(f"CRYPTOPIA_WIDGET:{json.dumps(spec)}", flush=True)


def _resolve(widget_id: str, default):
    """Read the value from the injected widget values dict, or use default.

    Cryptopia's runner injects `__cx_widget_values__` into the kernel's
    `__main__` module before re-running cells, so we look it up there.
    """
    values = _widget_values()
    return values.get(widget_id, default) if values is not None else default


def _widget_values() -> dict | None:
    try:
        import __main__
        v = getattr(__main__, "__cx_widget_values__", None)
        if not isinstance(v, dict):
            v = {}
            __main__.__cx_widget_values__ = v
        return v
    except Exception:
        return None


def _callbacks() -> dict | None:
    try:
        import __main__
        cbs = getattr(__main__, "__cx_callbacks__", None)
        if not isinstance(cbs, dict):
            cbs = {}
            __main__.__cx_callbacks__ = cbs
        return cbs
    except Exception:
        return None


def _register_callback(widget_id: str, callback: Callable[..., Any]) -> None:
    """Register an on_change handler for a widget id.

    Re-running a cell re-registers (replaces) the callback, which matches
    intuition: editing the cell's source updates the reactivity definition.
    Cells that produce widgets without on_change leave any previously
    registered callback in place — the user has explicitly opted out of
    auto-reactivity for that widget.
    """
    if callback is None:
        return
    cbs = _callbacks()
    if cbs is None:
        return
    cbs[widget_id] = callback


def _dispatch(widget_id: str, value: Any) -> None:
    """Backend-callable entry point for reactive updates.

    Called by `dispatch_widget` (FastAPI `/dispatch`). Updates the kernel's
    widget value table so subsequent SDK reads see the new value, then
    invokes the registered on_change callback (if any). The callback is
    free to call other `cx.*` primitives, which emit fresh widgets / display
    output the same way they would inside a cell run.

    A two-arg callable receives `(value, ctx)` where ctx exposes
    `widget_id`. A one-arg callable receives just `value`. A zero-arg
    callable is also allowed for cases where the new value is consulted
    via `__cx_widget_values__` directly.
    """
    values = _widget_values()
    if values is not None:
        values[widget_id] = value

    cbs = _callbacks()
    if cbs is None:
        return
    cb = cbs.get(widget_id)
    if cb is None:
        return

    try:
        # Best-effort arity inspection so authors can pick the shape they
        # like without forcing a `**kwargs` everywhere.
        import inspect
        sig = inspect.signature(cb)
        n = len([
            p for p in sig.parameters.values()
            if p.kind
            in (inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ])
    except (TypeError, ValueError):
        n = 1

    if n == 0:
        cb()
    elif n == 1:
        cb(value)
    else:
        cb(value, {"widget_id": widget_id})


def slider(
    label: str,
    min: float = 0,
    max: float = 100,
    value: float = 50,
    step: float = 1,
    on_change: Callable[..., Any] | None = None,
    key: str | None = None,
) -> float:
    """Render a slider widget and return its current value.

    Pass ``on_change=fn`` to react to slider movements without re-running
    the whole cell — the frontend will POST `/dispatch` and the kernel will
    invoke ``fn(new_value)`` with the SDK's stdout still piped to the page.
    """
    wid = key or _widget_id("slider", label)
    resolved = float(_resolve(wid, value))
    _emit({
        "type": "slider", "id": wid, "label": label,
        "value": resolved, "min": min, "max": max, "step": step,
        "has_callback": on_change is not None,
    })
    _register_callback(wid, on_change)
    return resolved


def select(
    label: str,
    options: list[str],
    value: str | None = None,
    on_change: Callable[..., Any] | None = None,
    key: str | None = None,
) -> str:
    """Render a dropdown and return the selected option."""
    default = value or (options[0] if options else "")
    wid = key or _widget_id("select", label)
    resolved = str(_resolve(wid, default))
    if options and resolved not in options:
        resolved = default
    _emit({
        "type": "select", "id": wid, "label": label,
        "value": resolved, "options": options,
        "has_callback": on_change is not None,
    })
    _register_callback(wid, on_change)
    return resolved


def text_input(
    label: str,
    value: str = "",
    placeholder: str = "",
    on_change: Callable[..., Any] | None = None,
    key: str | None = None,
) -> str:
    """Render a text input and return its current value."""
    wid = key or _widget_id("text_input", label)
    resolved = str(_resolve(wid, value))
    _emit({
        "type": "text_input", "id": wid, "label": label,
        "value": resolved, "placeholder": placeholder,
        "has_callback": on_change is not None,
    })
    _register_callback(wid, on_change)
    return resolved


def button(
    label: str,
    on_click: Callable[..., Any] | None = None,
    key: str | None = None,
) -> bool:
    """Render a button and return True if it was clicked.

    For symmetry with the other widgets, ``on_click`` registers an on_change
    callback bound to the click event (``value=True``).
    """
    wid = key or _widget_id("button", label)
    _emit({
        "type": "button", "id": wid, "label": label,
        "has_callback": on_click is not None,
    })
    _register_callback(wid, on_click)
    return bool(_resolve(wid, False))


def checkbox(
    label: str,
    value: bool = False,
    on_change: Callable[..., Any] | None = None,
    key: str | None = None,
) -> bool:
    """Render a checkbox and return its checked state."""
    wid = key or _widget_id("checkbox", label)
    resolved = bool(_resolve(wid, value))
    _emit({
        "type": "checkbox", "id": wid, "label": label,
        "value": resolved,
        "has_callback": on_change is not None,
    })
    _register_callback(wid, on_change)
    return resolved


def chart(option: dict, height: int = 400, key: str | None = None):
    """
    Render an ECharts chart.
    `option` is a standard ECharts option dict.
    """
    title = ""
    try:
        t = option.get("title")
        if isinstance(t, dict):
            title = str(t.get("text") or t.get("subtext") or "")
        elif isinstance(t, list) and t:
            title = str(t[0].get("text") or "") if isinstance(t[0], dict) else ""
    except Exception:
        pass
    wid = key or _widget_id("chart", title)
    _emit({"type": "chart", "id": wid, "option": option, "height": height})


def dataframe(
    df,
    title: str = "",
    key: str | None = None,
):
    """
    Render a pandas DataFrame as an interactive table.
    `df` can be a pandas DataFrame or a list of dicts.
    """
    wid = key or _widget_id("dataframe", title)
    try:
        import pandas as pd
        if isinstance(df, pd.DataFrame):
            columns = list(df.columns)
            data = df.values.tolist()
        else:
            raise TypeError
    except (ImportError, TypeError):
        if isinstance(df, list) and df and isinstance(df[0], dict):
            columns = list(df[0].keys())
            data = [[row.get(c) for c in columns] for row in df]
        else:
            columns = ["value"]
            data = [[str(v)] for v in df]

    _emit({"type": "dataframe", "id": wid, "columns": columns, "data": data, "title": title})


def text(content: str, format: str = "markdown", key: str | None = None):
    """
    Render text/markdown/latex output as a widget.
    `format` is one of 'plain', 'markdown', 'latex'.
    """
    wid = key or _widget_id("text", content[:40])
    _emit({"type": "text", "id": wid, "content": content, "format": format})


def latex(formula: str, key: str | None = None):
    """Render a LaTeX formula as a display widget."""
    text(f"$${formula}$$", format="latex", key=key)

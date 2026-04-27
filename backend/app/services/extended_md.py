"""
Cryptopia Extended Markdown — server-side parser, output splicer, and ipynb
importer. Spec: docs/extended-markdown.md

The TypeScript counterpart at frontend/src/lib/md/extended.ts is the
authoritative parser used by the editor and viewer. This module provides
the subset the backend needs:

- Walk fenced code blocks to extract runnable cells.
- Splice cx-output blocks into source_md after a cell runs.
- Pull a small metadata summary (title, description, interactive flag, tags).
- Convert a parsed Jupyter notebook (.ipynb) to extended markdown for import.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator


FENCE_RE = re.compile(r"^(```+|~~~+)(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Strip optional YAML frontmatter from `text`. Returns (frontmatter_dict, body).
    Supports the small YAML subset used by Cryptopia pages: scalars, booleans,
    integers, quoted strings, and flat lists `[a, b, c]`.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("---\n") and text != "---":
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    yaml_src = text[4:end]
    after = text[end + 4 :]
    body = after[1:] if after.startswith("\n") else after
    return _parse_yaml_block(yaml_src), body


def _parse_yaml_block(yaml: str) -> dict:
    out: dict = {}
    for line in yaml.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        out[m.group(1)] = _parse_scalar(m.group(2).strip())
    return out


def _parse_scalar(raw: str):
    if raw == "" or raw == "~" or raw == "null":
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(s) for s in _split_yaml_list(inner)]
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    return raw


def _split_yaml_list(inner: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    buf = ""
    in_str: str | None = None
    for ch in inner:
        if in_str:
            buf += ch
            if ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            buf += ch
            continue
        if ch == "[":
            depth += 1
        if ch == "]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


def serialize_frontmatter(fm: dict) -> str:
    if not fm:
        return ""
    ordered = ["title", "description", "tags", "interactive", "slug"]
    seen: set[str] = set()
    lines = ["---"]
    for k in ordered:
        if k in fm:
            lines.append(f"{k}: {_stringify_scalar(fm[k])}")
            seen.add(k)
    for k, v in fm.items():
        if k in seen:
            continue
        lines.append(f"{k}: {_stringify_scalar(v)}")
    lines.append("---")
    return "\n".join(lines)


def _stringify_scalar(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_stringify_scalar(v) for v in value) + "]"
    s = str(value)
    if s == "" or re.search(r"[:#\[\]{},&*!|>'\"%@`]", s) or s != s.strip():
        return json.dumps(s)
    return s


# ---------------------------------------------------------------------------
# Fence walking
# ---------------------------------------------------------------------------

@dataclass
class Fence:
    """A fenced code block discovered in source_md."""
    open_line: int           # line index of the opening fence
    close_line: int          # line index of the closing fence (or len(lines))
    info: str                # info string (everything after the opening backticks)
    body: str                # block content (without fences), without trailing newline
    lang: str = ""
    classes: list[str] = field(default_factory=list)
    id: str | None = None
    attrs: dict[str, str] = field(default_factory=dict)


def walk_fences(source_md: str) -> Iterator[Fence]:
    """Yield each top-level fenced block in document order."""
    text = source_md.replace("\r\n", "\n").replace("\r", "\n")
    _, body = parse_frontmatter(text)
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        marker = m.group(1)
        info = m.group(2).strip()
        start = i + 1
        end = start
        while end < len(lines) and not lines[end].startswith(marker):
            end += 1
        body_text = "\n".join(lines[start:end])
        fence = Fence(open_line=i, close_line=end, info=info, body=body_text)
        _populate_attrs(fence)
        yield fence
        i = end + 1 if end < len(lines) else end


def _populate_attrs(fence: Fence) -> None:
    info = fence.info
    if not info:
        return
    m = re.match(r"^([^\s{]*)\s*\{([^}]*)\}\s*$", info)
    if m:
        fence.lang = m.group(1)
        for tok in _tokenize_attrs(m.group(2).strip()):
            if tok.startswith("."):
                fence.classes.append(tok[1:])
            elif tok.startswith("#"):
                fence.id = tok[1:]
            elif "=" in tok:
                k, v = tok.split("=", 1)
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                fence.attrs[k] = v
    else:
        fence.lang = info.split(None, 1)[0] if info.split() else ""


def _tokenize_attrs(inner: str) -> list[str]:
    tokens: list[str] = []
    buf = ""
    in_str: str | None = None
    for ch in inner:
        if in_str:
            buf += ch
            if ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            buf += ch
            continue
        if ch.isspace():
            if buf:
                tokens.append(buf)
            buf = ""
        else:
            buf += ch
    if buf:
        tokens.append(buf)
    return tokens


# ---------------------------------------------------------------------------
# Code cell extraction
# ---------------------------------------------------------------------------

@dataclass
class CodeCell:
    """A runtime code cell — fenced block with the `.run` class.

    Distinct from a "code block" (display-only fenced source). Only code
    cells participate in execution; display code blocks are handled the
    same as any other markdown primitive.
    """
    id: str
    source: str
    auto: bool
    lang: str = "python"


def _is_code_cell_fence(fence: Fence) -> bool:
    if fence.lang in ("cx-output", "cx-widget"):
        return False
    return "run" in fence.classes


def extract_code_cells(source_md: str) -> list[CodeCell]:
    """
    Return code cells in order. Each `.run` fenced block becomes a CodeCell;
    cells without an explicit `#id` get auto-assigned `cell-1`, `cell-2`, ...
    A cell with `auto=false` is still returned, but callers may skip it on a
    "run all" pass. The widget injection / single-cell run paths always run a
    specific cell by id.
    """
    cells: list[CodeCell] = []
    used_ids: set[str] = set()
    counter = 1

    for fence in walk_fences(source_md):
        if not _is_code_cell_fence(fence):
            continue
        cell_id = fence.id
        if not cell_id:
            while f"cell-{counter}" in used_ids:
                counter += 1
            cell_id = f"cell-{counter}"
            counter += 1
        used_ids.add(cell_id)
        auto = fence.attrs.get("auto", "true").lower() != "false"
        cells.append(CodeCell(
            id=cell_id,
            source=fence.body,
            auto=auto,
            lang=fence.lang or "python",
        ))
    return cells


def is_interactive(source_md: str) -> bool:
    """A page is interactive if it has at least one code cell."""
    for fence in walk_fences(source_md):
        if _is_code_cell_fence(fence):
            return True
    return False


# ---------------------------------------------------------------------------
# Output splicing
# ---------------------------------------------------------------------------

def splice_output(source_md: str, cell_id: str, records: Iterable[dict]) -> str:
    """
    Replace (or insert) the cx-output block for `cell_id` with the given JSONL
    records. Records that fail to JSON-encode are dropped. If `cell_id` does
    not match any code cell, returns `source_md` unchanged.
    """
    text = source_md.replace("\r\n", "\n").replace("\r", "\n")
    fm_prefix, body = _split_frontmatter(text)
    lines = body.split("\n")
    fences = list(walk_fences(text))

    target_fence = None
    target_index = -1
    for idx, f in enumerate(fences):
        if not _is_code_cell_fence(f):
            continue
        if f.id == cell_id:
            target_fence = f
            target_index = idx
            break
    if target_fence is None:
        # Try auto-numbered match for cells that had no explicit `#id`.
        counter = 1
        for idx, f in enumerate(fences):
            if not _is_code_cell_fence(f):
                continue
            implicit_id = f.id or f"cell-{counter}"
            if not f.id:
                counter += 1
            if implicit_id == cell_id:
                target_fence = f
                target_index = idx
                break

    if target_fence is None:
        return source_md

    encoded_records = []
    for r in records:
        try:
            encoded_records.append(json.dumps(r, ensure_ascii=False))
        except (TypeError, ValueError):
            continue
    output_block_lines = [
        f"```cx-output {{for={cell_id}}}",
        *encoded_records,
        "```",
    ]

    next_fence = fences[target_index + 1] if target_index + 1 < len(fences) else None
    has_existing_output = (
        next_fence is not None
        and next_fence.lang == "cx-output"
        and (next_fence.attrs.get("for") == cell_id or next_fence.attrs.get("for") is None)
    )

    insert_after_close = target_fence.close_line + 1
    if has_existing_output:
        # Replace existing block from its open_line through close_line + blank trailers.
        del_start = next_fence.open_line
        del_end = next_fence.close_line + 1
        # Walk back over blank lines between target close and next open
        while del_start - 1 > target_fence.close_line and lines[del_start - 1].strip() == "":
            del_start -= 1
        new_lines = (
            lines[:target_fence.close_line + 1]
            + [""]
            + output_block_lines
            + lines[del_end:]
        )
    else:
        # Insert a blank line then the output block.
        new_lines = (
            lines[:insert_after_close]
            + [""]
            + output_block_lines
            + lines[insert_after_close:]
        )

    new_body = "\n".join(new_lines).rstrip("\n") + "\n"
    return fm_prefix + new_body


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split text into (frontmatter_prefix_with_trailing_newline, body)."""
    if not (text.startswith("---\n") or text == "---"):
        return "", text
    idx = text.find("\n---", 4)
    if idx < 0:
        return "", text
    after = text[idx + 4 :]
    if after.startswith("\n"):
        return text[: idx + 4 + 1], after[1:]
    return text[: idx + 4], after


def clear_outputs(source_md: str) -> str:
    """Remove all cx-output blocks from source_md."""
    text = source_md.replace("\r\n", "\n").replace("\r", "\n")
    fences = list(walk_fences(text))
    if not fences:
        return source_md

    fm_prefix, body = _split_frontmatter(text)
    lines = body.split("\n")

    spans_to_remove: list[tuple[int, int]] = []
    for f in fences:
        if f.lang == "cx-output":
            start = f.open_line
            end = f.close_line + 1
            while start > 0 and lines[start - 1].strip() == "":
                start -= 1
            spans_to_remove.append((start, end))

    new_lines: list[str] = []
    cursor = 0
    for start, end in spans_to_remove:
        new_lines.extend(lines[cursor:start])
        cursor = end
    new_lines.extend(lines[cursor:])

    return fm_prefix + "\n".join(new_lines).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

def derive_metadata(source_md: str) -> dict:
    """
    Quick scan returning {title, description, tags, is_interactive}. The
    frontmatter wins; otherwise we look for the first H1 heading and the first
    non-heading paragraph.
    """
    fm, body = parse_frontmatter(source_md)
    title = fm.get("title")
    description = fm.get("description")
    tags = fm.get("tags") or []
    interactive = fm.get("interactive")

    if title is None or description is None:
        for line in body.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if title is None and stripped.startswith("# ") and not stripped.startswith("## "):
                title = stripped[2:].strip()
                continue
            if description is None and not stripped.startswith("#") and not stripped.startswith("```"):
                description = stripped[:300]
                if title is not None:
                    break

    if interactive is None:
        interactive = is_interactive(source_md)

    return {
        "title": title,
        "description": description,
        "tags": [str(t) for t in tags] if tags else [],
        "is_interactive": bool(interactive),
    }


# ---------------------------------------------------------------------------
# Jupyter notebook → extended markdown
# ---------------------------------------------------------------------------

WIDGET_PREFIX = "CRYPTOPIA_WIDGET:"


def from_nbformat(nb: dict, *, default_lang: str = "python") -> str:
    """
    Convert a Jupyter notebook dict (nbformat v4) to Cryptopia Extended Markdown.

    - Markdown cells become prose blocks verbatim.
    - Code cells become fenced cells. Cells that import the cryptopia SDK or
      emit a `CRYPTOPIA_WIDGET:` line are tagged `.run` so they execute.
    - Stored `outputs` for runnable cells are converted to a `cx-output` block
      directly underneath, so the imported page can be viewed without re-running.
    """
    lines: list[str] = []
    title: str | None = None
    description: str | None = None

    kernel = (nb.get("metadata", {}).get("kernelspec") or {}).get("name", default_lang)
    if kernel.startswith("python"):
        kernel = "python"
    elif kernel == "ir":
        kernel = "r"

    cells = nb.get("cells", [])
    cell_index = 1

    for cell in cells:
        cell_type = cell.get("cell_type")
        source = _coerce(cell.get("source", ""))
        source = source.rstrip("\n")
        if cell_type == "markdown":
            lines.append(source)
            if title is None:
                m = re.search(r"^#\s+(.+)$", source, re.MULTILINE)
                if m:
                    title = m.group(1).strip()
            if description is None and source:
                for ln in source.split("\n"):
                    s = ln.strip()
                    if s and not s.startswith("#"):
                        description = s[:300]
                        break
        elif cell_type == "code":
            cell_id = f"cell-{cell_index}"
            cell_index += 1
            head = "```" + kernel + " {.run #" + cell_id + "}"
            lines.append(head)
            lines.append(source)
            lines.append("```")

            output_records = _convert_outputs(cell.get("outputs", []))
            if output_records:
                lines.append("")
                lines.append(f"```cx-output {{for={cell_id}}}")
                for rec in output_records:
                    lines.append(json.dumps(rec, ensure_ascii=False))
                lines.append("```")
        elif cell_type == "raw":
            lines.append(source)

        lines.append("")  # blank line between blocks

    fm: dict = {}
    if title:
        fm["title"] = title
    if description:
        fm["description"] = description
    interactive = any(c.get("cell_type") == "code" for c in cells)
    if interactive:
        fm["interactive"] = True

    body = "\n".join(lines).rstrip("\n") + "\n"
    if fm:
        return serialize_frontmatter(fm) + "\n\n" + body
    return body


def _coerce(value) -> str:
    if isinstance(value, list):
        return "".join(value)
    return str(value or "")


def _convert_outputs(outputs: list) -> list[dict]:
    """Map Jupyter cell outputs into Cryptopia output records."""
    records: list[dict] = []
    for out in outputs:
        ot = out.get("output_type")
        if ot == "stream":
            text = _coerce(out.get("text", ""))
            for line in text.splitlines():
                if line.startswith(WIDGET_PREFIX):
                    try:
                        spec = json.loads(line[len(WIDGET_PREFIX):])
                        records.append({"type": "widget", "spec": spec})
                    except Exception:
                        pass
                elif line:
                    records.append({"mime": "text/plain", "data": line + "\n"})
        elif ot in ("display_data", "execute_result"):
            data = out.get("data") or {}
            if "image/png" in data:
                records.append({"mime": "image/png", "data": _coerce(data["image/png"])})
            elif "image/svg+xml" in data:
                records.append({"mime": "image/svg+xml", "data": _coerce(data["image/svg+xml"])})
            elif "text/html" in data:
                records.append({"mime": "text/html", "data": _coerce(data["text/html"])})
            elif "application/json" in data:
                records.append({"mime": "application/json", "data": json.dumps(data["application/json"])})
            elif "text/plain" in data:
                records.append({"mime": "text/plain", "data": _coerce(data["text/plain"])})
        elif ot == "error":
            records.append({
                "type": "error",
                "ename": out.get("ename", ""),
                "evalue": out.get("evalue", ""),
                "traceback": out.get("traceback", []),
            })
    return records

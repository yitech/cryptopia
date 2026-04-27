# Cryptopia Extended Markdown

Cryptopia pages are stored, edited, exported and imported as a single Markdown
file with a small set of well-defined extensions. Any compliant CommonMark or
GitHub Flavored Markdown (GFM) renderer (e.g. github.com, VS Code preview) will
display the file with all prose, math and code visible. Only the Cryptopia
render engine interprets the executable cells, cached outputs and standalone
widgets.

This document is the normative spec; the canonical parser / serializer pair
lives at:

- `frontend/src/lib/md/extended.ts` (TypeScript, used by the editor and the SSR
  viewer)
- `backend/app/services/extended_md.py` (Python, used by the execution service
  and the importer)

Both implementations must round-trip the same file byte-equivalently up to
normalization of trailing whitespace and final newline.

## File structure

A page is a UTF-8 text file with three top-level regions:

```
[ optional YAML frontmatter ]
[ page body — CommonMark + GFM + KaTeX + Cryptopia fences ]
```

### 1. Frontmatter

A page may begin with a YAML frontmatter block delimited by `---`:

```yaml
---
title: Gradient Descent Visualisation
description: Interactive exploration with sliders.
tags: [optimisation, ml]
interactive: true
---
```

Recognized keys:

| Key            | Type            | Default | Notes                                                  |
| -------------- | --------------- | ------- | ------------------------------------------------------ |
| `title`        | string          | (none)  | Falls back to the first `# H1`, then to the file slug. |
| `description`  | string          | (none)  | Falls back to the first non-heading paragraph.         |
| `tags`         | list of strings | `[]`    | Free-form taxonomy tags.                               |
| `interactive`  | bool            | auto    | If unset, derived from presence of `.run` cells.       |
| `slug`         | string          | (none)  | Optional override; otherwise generated server-side.    |

Unknown keys are preserved on round-trip but ignored by the renderer.

### 2. Body

Standard CommonMark applies, plus:

- **GFM** — tables, strikethrough, task lists, autolinks.
- **Math** via KaTeX — `$...$` for inline, `$$...$$` for display.
- **GFM alerts** — `> [!note]`, `> [!warning]`, etc., render as callouts.

## Code blocks vs. code cells

Cryptopia distinguishes two **separate** primitives that share the fenced-code
syntax:

- **Code block** — the Markdown primitive. Display-only, syntax-highlighted,
  no execution, no id, no output. Internally `kind: 'code-block'`.
- **Code cell** — a runtime component. Has a stable id, may declare
  dependencies, produces outputs and widgets. Internally `kind: 'code-cell'`.
  In the rendered page the source is **collapsed by default** — readers see
  the cell's outputs and widgets, not its implementation, unless they choose
  "Show sources".

The on-disk distinction is the presence of the `.run` class in the info
string. Both shapes are syntactically valid Markdown so the file remains
readable on github.com.

```markdown
\`\`\`python
# Code block — display only.
def f(x): return x * x
\`\`\`

\`\`\`python {.run #compute}
# Code cell — executes, may emit widgets via the cryptopia SDK.
import cryptopia as cx
alpha = cx.slider("alpha", 0, 1, 0.5)
\`\`\`
```

## Cryptopia fence extensions

Three fenced code-block conventions extend a plain Markdown file. They are
syntactically standard fenced blocks; the magic lives entirely in the *info
string* (the text after the opening backticks).

### Executable code cell (`{.run}`)

Mark a fenced code block executable by adding the `.run` class:

````markdown
```python {.run #cell-alpha}
import cryptopia as cx
alpha = cx.slider("Learning rate", 0.001, 0.1, 0.01)
print(alpha)
```
````

Info-string grammar (a subset of Pandoc attribute syntax):

```
LANG { CLASSES IDENT KEYS }
CLASSES = ('.' IDENT)*
IDENT   = '#' [A-Za-z0-9_-]+
KEYS    = (IDENT '=' VALUE)*
```

Recognized attributes:

- `.run` — required to mark the block as a code cell. Without it the block
  is a plain display code block.
- `#id` — stable identifier for binding cached outputs. If omitted, the
  serializer generates `cell-N` based on document order, so editing prose
  between cells does not break bindings.
- `auto=false` — opt out of running this cell on the publish-time "Run all".
  Useful for cells that should only run when an upstream widget changes.

### Cached output block

Outputs produced by the most recent execution of a cell are stored in a fenced
block immediately following the cell, with info string `cx-output {for=ID}`:

````markdown
```cx-output {for=cell-alpha}
{"type":"widget","spec":{"type":"slider","id":"slider_a1","label":"Learning rate","min":0.001,"max":0.1,"value":0.01,"step":0.001}}
{"mime":"text/plain","data":"0.01\n"}
```
````

Each line is a single JSON value, JSONL-style. Two record shapes are defined:

- **Stream / display data**:
  ```json
  {"mime":"text/plain","data":"…"}
  ```
  `mime` is one of `text/plain`, `text/html`, `image/png` (base64),
  `image/svg+xml`, `application/json`. The renderer maps each MIME to the same
  branches as today's Jupyter `OutputCell.svelte`.

- **Widget**:
  ```json
  {"type":"widget","spec":{...}}
  ```
  `spec` is a `WidgetSpec` (see `frontend/src/lib/stores/execution.ts`). The
  renderer hands it to `WidgetRenderer.svelte`. When the page is opened in
  static mode, sliders/buttons are still drawn but adjusting them only emits
  local state until a kernel is connected.

- **Error**:
  ```json
  {"type":"error","ename":"…","evalue":"…","traceback":["…"]}
  ```

A cell with no output may omit the `cx-output` block entirely.

### Standalone widget block

A widget with no associated code cell — useful for static charts, dataframes
embedded as data, or display-only LaTeX:

````markdown
```cx-widget
{"type":"chart","option":{"xAxis":{"data":[0,1,2]},"series":[{"type":"line","data":[0,1,4]}]}}
```
````

The body is exactly one JSON value matching `WidgetSpec`.

## Parser semantics

1. Strip optional YAML frontmatter.
2. Run a CommonMark + GFM + math parser on the remaining body, producing an
   AST of standard Markdown nodes.
3. Walk fenced code blocks. For each one, parse the info string. Classify into:
   - `code-cell` (`{.run …}`)
   - `cx-output`
   - `cx-widget`
   - `code-block` (everything else — rendered with Shiki, no execution).
4. After the walk, attach each `cx-output {for=ID}` block to its matching
   `code-cell` (by `#id`) and remove it from the top-level block list. Output
   blocks that have no matching cell are kept as plain code blocks (so the
   file remains self-contained even if you delete the owning cell by hand).
5. Compute `interactive` (if not set in frontmatter) as: any `code-cell` is
   present.

## Serializer guarantees

- **Stable cell IDs**. If a cell has no explicit `#id`, the serializer assigns
  `cell-1`, `cell-2`, … in document order. Once assigned, an ID is preserved
  across edits as long as the cell exists.
- **Output adjacency**. A cell's `cx-output` block, if present, is always
  emitted on the line immediately after the cell.
- **Frontmatter order**. Frontmatter keys are emitted in this order: `title`,
  `description`, `tags`, `interactive`, `slug`, then any extra keys.
- **Final newline**. Files end with exactly one trailing newline.
- **Idempotence**. `serialize(parse(s)) == s` for any file produced by the
  serializer.

## Runtime contract

The rendered page interacts with a per-page Python kernel via **two HTTP
endpoints**. There is no WebSocket; every request returns a complete output
list and the renderer folds that into per-cell state.

| Path                                  | When                                            | Body                                  |
| ------------------------------------- | ----------------------------------------------- | ------------------------------------- |
| `POST /api/pages/id/{id}/run-cell`    | First run, "Re-run page", per-cell Run button   | `{cell_id, widget_values}` → `{outputs, error, source_md}` |
| `POST /api/pages/id/{id}/dispatch`    | An input widget changed and declared `on_change`| `{widget_id, value}` → `{outputs, error}` |

`run-cell` executes one code cell against the persistent kernel. The kernel
keeps state across requests, so a cell that imports modules or defines
helpers in the first run remains available for the next dispatch.

`dispatch` calls `cryptopia._dispatch(widget_id, value)` against the kernel.
That helper updates `__cx_widget_values__[widget_id]` and invokes the
`on_change` callback registered for the widget by a previous cell run. The
callback is free to call any `cx.*` primitive, and any widgets / display data
it produces are captured and returned the same way as a cell run's output.

Drafts are author-only; published pages are runnable by any visitor. Only the
author's runs splice the resulting outputs back into `source_md` (as
`cx-output` blocks) — viewer runs are stateless from the page's perspective.

## Reactivity model: explicit `on_change`

The SDK extends each input widget with an `on_change=` parameter:

```python
import cryptopia as cx

def update_chart(v):
    cx.chart({...}, key="chart-1")

alpha = cx.slider("alpha", min=0, max=1, value=0.5, on_change=update_chart)
update_chart(alpha)  # initial render
```

When the user moves the slider in the browser, the frontend POSTs
`/dispatch` with `{widget_id: 'slider_alpha_…', value: 0.7}`. The kernel
runs `update_chart(0.7)`. The new chart's widget spec arrives as part of the
HTTP response and replaces the previous one in-place (matched by widget id).

A widget without `on_change` falls back to **re-running its owner cell** on
change. This is the simplest model — change a slider, the cell that emitted
it runs again — but the explicit callback is preferred because it lets a
single cell define both controls and the function that consumes them, and
the runtime only re-executes the minimum.

Callbacks are stored on `__main__.__cx_callbacks__` and overwritten each
time the owning cell re-runs (so editing the cell's source updates the
reactive definition). Cells whose source produces a widget without
`on_change` leave any previously registered callback in place — change is
explicit only.

## Minimal example

````markdown
---
title: Hello Cryptopia
tags: [demo]
---

# Hello, world

A tiny example. Inline math: $e^{i\pi} = -1$.

```python {.run #greet}
name = "Cryptopia"
print(f"Hello, {name}!")
```

```cx-output {for=greet}
{"mime":"text/plain","data":"Hello, Cryptopia!\n"}
```
````

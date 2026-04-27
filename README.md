# Cryptopia

**Interactive research publishing platform** — author block-based pages with live Jupyter widgets, render them online, or export them as a single self-contained markdown file.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | SvelteKit 2 + Svelte 5 + Tailwind CSS v4 |
| Backend | FastAPI + SQLAlchemy (async) + Alembic |
| Database | PostgreSQL 16 |
| Live execution | `jupyter_client` kernel pool |
| Math | KaTeX via `marked-katex-extension` |
| Code highlight | Shiki (one-dark-pro theme) |
| Charts | ECharts |
| Page format | Cryptopia Extended Markdown (see `docs/extended-markdown.md`) |
| SDK | `cryptopia` Python package |

## Quick start (Docker)

```bash
cp .env.example .env
# Edit .env and set a strong SECRET_KEY
docker compose up --build
```

Frontend: http://localhost:3000  
Backend API: http://localhost:8000/docs

## Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ../sdk   # install cryptopia SDK

cp ../.env.example .env

docker compose up db -d
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Authoring pages

Pages are stored as **Cryptopia Extended Markdown** — valid CommonMark + GFM + KaTeX with three small fenced extensions for executable code, cached outputs, and standalone widgets. The full grammar lives in [`docs/extended-markdown.md`](docs/extended-markdown.md).

There are three ways to create a page:

1. **Block editor** — go to `/publish` → **New page**. Drop in headings, prose, math, and runnable code blocks; click **Run** on any cell to execute against a live kernel and capture its outputs. The same content saves losslessly to `.md`.
2. **Import** — `/publish` → **Choose file** to upload an existing `.md` (extended markdown) or `.ipynb`. Notebooks are converted to extended markdown on import.
3. **Edit raw markdown** — every editor has a **Source** tab that round-trips to and from the same file format. You can also `curl /api/pages/<user>/<slug>/raw.md` to fetch the canonical source.

Once published, a page lives at `/research/<user>/<slug>`. Cached outputs render immediately; if the page contains runnable code, viewers can press **Run** to spin up a kernel and drive widgets live.

A worked example lives in [`examples/demo-research/research.md`](examples/demo-research/research.md).

## Interactive widgets

Inside a runnable code block, use the SDK to declare widgets and outputs:

```python
import cryptopia as cx

alpha = cx.slider("Learning rate", min=0.0001, max=0.1, value=0.01, step=0.0001)
optimizer = cx.select("Optimizer", ["SGD", "Adam", "RMSProp"])

cx.chart({
    "title": {"text": "Loss"},
    "xAxis": {"type": "category", "data": list(range(10))},
    "yAxis": {},
    "series": [{"type": "line", "data": [alpha * i for i in range(10)]}],
})

import pandas as pd
cx.dataframe(pd.DataFrame({"epoch": range(5), "loss": [0.5, 0.3, 0.2, 0.15, 0.1]}))

cx.latex(r"\mathcal{L}(\theta) = -\sum_i y_i \log \hat{y}_i")
```

When the cell runs, each widget is captured as a `cx-output` JSONL fence right after the code block. The viewer renders those cached widgets immediately and reattaches them to a live kernel when **Run** is pressed.

## Project structure

```
cryptopia/
├── frontend/                 # SvelteKit app
│   └── src/
│       ├── routes/
│       │   ├── edit/[id]/    # block editor
│       │   ├── publish/      # new / import / my pages
│       │   └── research/     # explore + reader view
│       └── lib/
│           ├── md/           # extended.ts parser/serializer
│           ├── components/
│           │   ├── notebook/ # MarkdownCell, CodeCell, OutputCell, BlockView
│           │   ├── editor/   # BlockEditor (per-block UI)
│           │   └── widgets/  # interactive widget components
│           └── stores/       # execution WS store
├── backend/
│   └── app/
│       ├── api/              # auth, pages, social
│       ├── services/         # extended_md, execution (kernel pool)
│       ├── models/           # User, Page, Tag, Comment, Reaction
│       └── core/             # config, database, auth
├── sdk/                      # cryptopia Python SDK
├── docs/
│   └── extended-markdown.md  # file format spec
├── examples/demo-research/
│   └── research.md           # demo page in extended markdown
├── docker-compose.yml
└── .env.example
```

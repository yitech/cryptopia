# Cryptopia

A modern, multi-user data dashboard platform built around [marimo](https://marimo.io)
notebooks. Researchers can author live, reactive dashboards in the browser and
publish them with permission control. Authentication is delegated to your
existing [Authelia](https://www.authelia.com) deployment via forward-auth, so
Cryptopia never has to care about passwords, MFA, or sessions.

## Features

- **Author** notebooks in the browser with the full marimo editor.
- **Publish** snapshots into a separate read-only space; viewers always see a
  stable version, never your work-in-progress.
- **Permission model** with two visibilities:
  - `public` — anyone can view a fully static (WASM-rendered) snapshot, but
    backend-powered interactions still require a logged-in user.
  - `team` — only Authelia group members listed on the notebook can view or
    interact with it.
- **Authelia integration** through forward-auth headers (`Remote-User`,
  `Remote-Email`, `Remote-Name`, `Remote-Groups`). Cryptopia trusts the
  reverse proxy to do the actual auth handshake.
- **Versioning**: every publish snapshot is stored with a hash and timestamp.
- **Per-notebook isolation**: editing spawns a dedicated `marimo edit`
  subprocess scoped to that notebook; running uses marimo's dynamic-directory
  ASGI app with a permission validator.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│ Browser                                                           │
└───────────────┬───────────────────────────────────────────────────┘
                │  HTTPS
                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Caddy / Traefik / nginx                                           │
│  ├─ TLS termination                                               │
│  └─ Authelia forward-auth → injects Remote-User / Remote-Groups   │
└───────────────┬───────────────────────────────────────────────────┘
                │  HTTP + headers
                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Cryptopia (FastAPI, port 8000)                                    │
│                                                                   │
│  /api/me              → identity from Authelia headers            │
│  /api/notebooks/...   → CRUD, publish, versions                   │
│  /api/edit/<id>/...   → reverse proxy to a per-notebook           │
│                          marimo-edit subprocess (HTTP + WS)       │
│  /run/<id>/...        → marimo run-mode ASGI app, gated by        │
│                          per-request validate_callback            │
│  /p/<id>/...          → static WASM bundle (no backend needed)    │
│  /...                 → SvelteKit static UI fallback              │
└──────────────────────────────────────────────────────────────────┘
```

The state Cryptopia owns:

| Path                       | Role                                           |
|----------------------------|-----------------------------------------------|
| `data/cryptopia.db`        | SQLite metadata (users, notebooks, versions)  |
| `data/notebooks/<user>/`   | Live working copies — only the owner can edit |
| `data/published/`          | The current published `.py` per notebook      |
| `data/published_static/`   | WASM bundles produced via `marimo export`     |
| `data/edit_sessions/`      | Reserved for per-session scratch              |

## Quick start (development)

The repo is a small monorepo: `backend/` (FastAPI + marimo), `frontend/`
(SvelteKit), and `deploy/` (Caddyfile, etc.). For local development you
typically run the two app processes side-by-side; the SvelteKit dev server
proxies `/api`, `/run`, and `/p` to the backend automatically.

### 1. Install Python deps

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e "backend[dev]"
```

### 2. Initialise the database

```bash
cd backend
alembic upgrade head
```

### 3. Run the backend

In dev mode you can fake an Authelia identity with the `CRYPTOPIA_DEV_AUTH_*`
env vars; in production these MUST be unset.

```bash
cd backend
CRYPTOPIA_DATA_DIR=../data \
CRYPTOPIA_DATABASE_URL=sqlite+aiosqlite:///../data/cryptopia.db \
CRYPTOPIA_DEV_AUTH_USER=alice \
CRYPTOPIA_DEV_AUTH_NAME="Alice Researcher" \
CRYPTOPIA_DEV_AUTH_GROUPS="researchers,admins" \
uvicorn app.main:app --reload --port 8000
```

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Visit <http://localhost:5173>. Vite proxies API/edit/run/static traffic to
the backend on port 8000.

### 5. Try it out

1. Click **New notebook** in the top-right.
2. Pick visibility (`team` keeps it scoped to Authelia groups; `public`
   makes a static WASM snapshot world-readable but interactive use still
   requires a login).
3. On the detail page click **Edit** — you'll see the marimo editor inside
   an iframe served via `/api/edit/<id>/`.
4. Click **Publish**. Cryptopia copies the working file to
   `data/published/`, snapshots it as a version, and kicks off a
   `marimo export html-wasm` in the background.
5. Click **Open dashboard** to use the live, reactive run-mode view.

## Production deployment

### Behind Authelia + Caddy

`docker-compose.yml` and `deploy/Caddyfile` give you a working baseline.
Adjust the hostnames (`dashboards.lynxlinkage.com`, `auth.lynxlinkage.com`),
plug in your TLS email, and:

```bash
# Build the static frontend bundle that the backend serves
( cd frontend && npm install && npm run build )

# Bring up the stack
docker compose up -d --build
```

The Caddyfile shows the two important rules:

1. `/p/*` and `/_app/*` (and the favicon) are served *without* triggering
   Authelia — that's what makes `public` notebooks viewable by anonymous
   visitors.
2. Every other path is protected by `forward_auth`, which copies
   `Remote-User`, `Remote-Email`, `Remote-Name`, and `Remote-Groups` onto
   the upstream request. Cryptopia reads those four headers and trusts
   them; it does not call Authelia itself.

### Behind an existing Traefik / nginx

Cryptopia doesn't care what proxy you use as long as it:

- Forwards traffic to the backend on the configured port.
- Sets `Remote-User`, `Remote-Email`, `Remote-Name`, `Remote-Groups`
  headers from Authelia for protected routes.
- Lets `/p/*` through *without* authentication (so anonymous static
  viewing works for `public` notebooks).
- Supports WebSocket upgrades (for the marimo editor and run modes).

If your Authelia is configured to use different header names, override
them via `CRYPTOPIA_AUTH_HEADER_USER`, etc.

## Permission model in detail

```
                ┌──────────────────────────────────────────┐
                │          What can <user> do?              │
                └──────────────────────────────────────────┘

   visibility   anonymous    other logged-in     team member    owner
   ─────────────────────────────────────────────────────────────────────
   public       view static  view + run live     view + run     full
                              ▲                  ▲              control
                              │                  │
                    "logged in => backend OK"
   team         (404)        (404)               view + run     full
```

- **Anyone** can view a `public` notebook's static WASM snapshot at
  `/p/<id>/`.
- A **logged-in user** can additionally hit `/run/<id>/`, which streams a
  live marimo session on the server.
- Only the **owner** can hit `/api/edit/<id>/`, which spawns/forwards a
  `marimo edit` subprocess.
- **Team-only** notebooks are completely invisible (404) to non-members
  to avoid leaking titles/descriptions.

## Configuration reference

| Variable                              | Default                                              | Purpose                              |
|---------------------------------------|------------------------------------------------------|--------------------------------------|
| `CRYPTOPIA_DATA_DIR`                  | `./data`                                             | Filesystem storage root              |
| `CRYPTOPIA_DATABASE_URL`              | `sqlite+aiosqlite:///./data/cryptopia.db`            | SQLAlchemy URL                       |
| `CRYPTOPIA_PUBLIC_URL`                | `http://localhost:8000`                              | Public hostname (used for OG)        |
| `CRYPTOPIA_AUTHELIA_URL`              | `https://auth.lynxlinkage.com`                       | Login redirect target                |
| `CRYPTOPIA_AUTH_HEADER_USER`          | `Remote-User`                                        | Header name override                 |
| `CRYPTOPIA_AUTH_HEADER_EMAIL`         | `Remote-Email`                                       | "                                    |
| `CRYPTOPIA_AUTH_HEADER_NAME`          | `Remote-Name`                                        | "                                    |
| `CRYPTOPIA_AUTH_HEADER_GROUPS`        | `Remote-Groups`                                      | "                                    |
| `CRYPTOPIA_DEV_AUTH_USER`             | (empty)                                              | Local dev auth bypass — leave empty in prod |
| `CRYPTOPIA_EDIT_IDLE_TIMEOUT`         | `1800`                                               | Seconds before idle edit subprocess is reaped |
| `CRYPTOPIA_EDIT_PORT_RANGE_START`     | `42000`                                              | Lower bound for edit subprocess ports |
| `CRYPTOPIA_EDIT_PORT_RANGE_END`       | `42999`                                              | Upper bound for edit subprocess ports |

See `.env.example` for a full reference.

## Tests & lint

```bash
# Backend
cd backend
ruff check .
pytest

# Frontend
cd frontend
npm run check
```

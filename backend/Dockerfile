FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/app /app/backend/app
COPY backend/alembic /app/backend/alembic
COPY backend/alembic.ini /app/backend/alembic.ini

RUN pip install -e /app/backend

COPY frontend/build /app/frontend/build

ENV CRYPTOPIA_DATA_DIR=/var/cryptopia \
    CRYPTOPIA_DATABASE_URL=sqlite+aiosqlite:////var/cryptopia/cryptopia.db

WORKDIR /app/backend
EXPOSE 8000

# Run migrations on container start, then exec uvicorn. We deliberately
# avoid `--reload` and any worker pool: marimo's edit/run subprocesses
# already do per-notebook isolation, and multi-worker uvicorn would mean
# each worker spawning duplicate marimo processes.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

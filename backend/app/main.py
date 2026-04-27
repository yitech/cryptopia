import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, Base
from app.api import auth, pages, social
from app.services.execution import kernel_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    _s = get_settings()
    if _s.jupyter_data_dir:
        os.environ.setdefault("JUPYTER_DATA_DIR", _s.jupyter_data_dir)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def evict_loop():
        while True:
            await asyncio.sleep(120)
            await kernel_pool.evict_idle()

    eviction_task = asyncio.create_task(evict_loop())

    yield

    eviction_task.cancel()
    await kernel_pool.shutdown_all()
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(social.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

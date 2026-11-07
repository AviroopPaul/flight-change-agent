import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.core.db import create_pool, migrate
from app.records.router import router as records_router

log = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pool = await create_pool(settings.database_url)
        app.state.http = httpx.AsyncClient(timeout=10)
        await migrate(app.state.pool)
        try:
            yield
        finally:
            await app.state.http.aclose()
            await app.state.pool.close()

    app = FastAPI(title="Flight change agent", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(records_router)

    @app.get("/health")
    async def health(request: Request):
        try:
            async with request.app.state.pool.acquire() as conn:
                db = await conn.fetchval("select 1") == 1
        except Exception:  # noqa: BLE001
            db = False
        return {"ok": True, "db": db}

    return app


app = create_app()

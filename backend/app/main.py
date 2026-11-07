import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.core.clock import now_ist
from app.core.db import create_pool, migrate
from app.core.tasks import spawn
from app.jobs.router import router as jobs_router
from app.jobs.service import sweep
from app.calls.livekit import LiveKitBridge
from app.calls.router import router as calls_router
from app.chat.hub import Hub
from app.chat.router import router as chat_router
from app.records.router import router as records_router
from app.sessions.router import router as sessions_router
from app.telemetry.router import router as telemetry_router

log = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pool = await create_pool(settings.database_url)
        own_http = getattr(app.state, "http", None) is None
        if own_http:
            app.state.http = httpx.AsyncClient(timeout=10)
        await migrate(app.state.pool)
        if settings.sweep_on_startup:
            spawn(app, sweep(app, now_ist()))  # startup recovery: deliver anything a restart left behind
        try:
            yield
        finally:
            for t in list(app.state.tasks):
                t.cancel()
            if own_http:
                await app.state.http.aclose()
            await app.state.pool.close()

    app = FastAPI(title="Flight change agent", lifespan=lifespan)
    app.state.settings = settings
    app.state.hub = Hub()
    app.state.tasks = set()
    app.state.livekit = LiveKitBridge(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(records_router)
    app.include_router(sessions_router)
    app.include_router(chat_router)
    app.include_router(calls_router)
    app.include_router(telemetry_router)
    app.include_router(jobs_router)

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

import os

import asyncpg
import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.core.config import Settings
from app.core.db import create_pool, migrate

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://dev:dev@localhost:5433/flight"
)
TEST_TOKEN = "test-service-token"


async def reset_schema() -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        service_token=TEST_TOKEN,
        livekit_url="wss://test.livekit.cloud",
        livekit_api_key="lk_test_key",
        livekit_api_secret="lk_test_secret_that_is_long_enough_123456",
        groq_api_key="gsk_test",
        allowed_origins=["http://localhost:5173"],
        stub_url="http://test/stub/records",
        chat_autostart_seconds=0,
        sweep_on_startup=False,
    )


@pytest.fixture
async def pool():
    await reset_schema()
    p = await create_pool(TEST_DATABASE_URL)
    await migrate(p)
    yield p
    await p.close()


@pytest.fixture
async def app(pool, settings):
    from app.main import create_app

    application = create_app(settings)
    async with LifespanManager(application):
        yield application


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

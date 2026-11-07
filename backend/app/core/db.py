import json
from pathlib import Path

import asyncpg
from fastapi import Request

DOMAIN_ORDER = ["sessions", "records", "telemetry"]
APP_DIR = Path(__file__).resolve().parent.parent


async def _init_conn(conn: asyncpg.Connection) -> None:
    for typ in ("jsonb", "json"):
        await conn.set_type_codec(
            typ, encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=10, init=_init_conn)


async def migrate(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        for domain in DOMAIN_ORDER:
            sql = (APP_DIR / domain / "tables.sql").read_text()
            await conn.execute(sql)


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool

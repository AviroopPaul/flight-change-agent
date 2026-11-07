import asyncpg

from app.telemetry import repository as repo
from app.telemetry.pricing import cost_usd

USAGE_KINDS = {"stt_seconds", "tts_chars", "llm_in_tokens", "llm_out_tokens", "call_seconds"}


async def session_cost(conn, session_id: str) -> float:
    return cost_usd(await repo.usage_rows(conn, session_id))


async def last_turns(pool: asyncpg.Pool, session_id: str, n: int = 20) -> list[dict]:
    async with pool.acquire() as conn:
        return await repo.last_turns(conn, session_id, n)


async def add_turn(pool: asyncpg.Pool, session_id: str, role: str, text: str) -> None:
    async with pool.acquire() as conn:
        await repo.add_turn(conn, session_id, role, text)


async def add_usage(pool: asyncpg.Pool, session_id: str, kind: str, quantity: float) -> None:
    async with pool.acquire() as conn:
        await repo.add_usage(conn, session_id, kind, quantity)


async def add_metrics(pool: asyncpg.Pool, session_id: str, eou: float, ttft: float, ttfb: float) -> None:
    async with pool.acquire() as conn:
        await repo.add_metrics(conn, session_id, eou, ttft, ttfb)


async def last_signal(pool: asyncpg.Pool, session_id: str):
    async with pool.acquire() as conn:
        return await repo.last_signal(conn, session_id)

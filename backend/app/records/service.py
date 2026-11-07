"""Record outbox and delivery."""

import json
import logging

import asyncpg
import httpx

from app.core.clock import now_ist
from app.records import repository as repo

log = logging.getLogger("records")


async def save_record(conn, session_id: str, record: dict) -> None:
    await repo.insert_record(conn, session_id, record["revision"], record["outcome"], record)


async def deliver_pending(pool: asyncpg.Pool, http: httpx.AsyncClient, stub_url: str, token: str = "") -> int:
    """POST each undelivered record once. Safe to run concurrently and after a restart."""
    delivered = 0
    failed: set[tuple[str, int]] = set()
    while True:
        async with pool.acquire() as conn, conn.transaction():
            row = await repo.claim_undelivered(conn)
            if row is None or (row["session_id"], row["revision"]) in failed:
                return delivered
            sid, rev, record = row["session_id"], row["revision"], row["payload"]
            key = f"{sid}:{rev}"
            try:
                resp = await http.post(stub_url, json=record, headers={
                    "Idempotency-Key": key, "Authorization": f"Bearer {token}"})
                ok = 200 <= resp.status_code < 300
            except httpx.HTTPError as exc:
                log.warning("record delivery failed for %s: %s", key, exc)
                ok = False
            if ok:
                await repo.mark_delivered(conn, sid, rev, now_ist())
                log.info("RECORD %s", json.dumps(record, ensure_ascii=False))
                delivered += 1
            else:
                await repo.bump_attempts(conn, sid, rev)
                failed.add((sid, rev))


async def stub_receive(pool: asyncpg.Pool, key: str, payload: dict) -> bool:
    async with pool.acquire() as conn:
        return await repo.stub_insert(conn, key, payload)


async def stub_list(pool: asyncpg.Pool, session_id: str | None) -> list[dict]:
    async with pool.acquire() as conn:
        return await repo.stub_list(conn, session_id)


async def latest_record(pool: asyncpg.Pool, session_id: str) -> dict | None:
    async with pool.acquire() as conn:
        return await repo.latest_record(conn, session_id)

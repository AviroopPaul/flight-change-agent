"""SQL for the records outbox and the stub receiver."""

from datetime import datetime


async def insert_record(conn, session_id: str, revision: int, outcome: str, payload: dict) -> None:
    await conn.execute(
        "insert into records (session_id, revision, outcome, payload) values ($1, $2, $3, $4)"
        " on conflict (session_id, revision) do nothing",
        session_id, revision, outcome, payload,
    )


async def claim_undelivered(conn):
    return await conn.fetchrow(
        "select session_id, revision, payload from records where delivered_at is null and attempts < 20"
        " order by created_at for update skip locked limit 1")


async def mark_delivered(conn, session_id: str, revision: int, now: datetime) -> None:
    await conn.execute(
        "update records set delivered_at = $3 where session_id = $1 and revision = $2", session_id, revision, now)


async def bump_attempts(conn, session_id: str, revision: int) -> None:
    await conn.execute(
        "update records set attempts = attempts + 1 where session_id = $1 and revision = $2", session_id, revision)


async def stub_insert(conn, key: str, payload: dict) -> bool:
    """True if stored, False if the key was seen before."""
    rid = await conn.fetchval(
        "insert into stub_records (idempotency_key, payload) values ($1, $2)"
        " on conflict (idempotency_key) do nothing returning id", key, payload)
    return rid is not None


async def stub_list(conn, session_id: str | None, limit: int = 50) -> list[dict]:
    if session_id:
        rows = await conn.fetch(
            "select idempotency_key, payload, received_at from stub_records where payload->>'sessionId' = $1"
            " order by id desc", session_id)
        return [{"idempotencyKey": r["idempotency_key"], "receivedAt": r["received_at"].isoformat(),
                 "record": r["payload"]} for r in rows]
    rows = await conn.fetch(
        "select idempotency_key, payload->>'outcome' as outcome, received_at from stub_records"
        " order by id desc limit $1", limit)
    return [{"idempotencyKey": r["idempotency_key"], "outcome": r["outcome"],
             "receivedAt": r["received_at"].isoformat()} for r in rows]


async def latest_record(conn, session_id: str) -> dict | None:
    return await conn.fetchval(
        "select payload from records where session_id = $1 order by revision desc limit 1", session_id)


async def revisions(conn, session_id: str) -> list[dict]:
    rows = await conn.fetch("select revision, outcome, created_at, delivered_at, attempts from records"
                            " where session_id = $1 order by revision", session_id)
    return [dict(r) for r in rows]

"""SQL for the sessions and events tables. Nothing else in the app touches them."""

from datetime import datetime

import asyncpg

TRANSIENT_KINDS = {"inputError"}


async def insert_session(conn, session_id: str, ip_hash: str, now: datetime, state: dict) -> None:
    await conn.execute(
        "insert into sessions (id, created_at, updated_at, ip_hash, last_user_activity_at, state, version)"
        " values ($1, $2, $2, $3, $2, $4, 0)",
        session_id, now, ip_hash, state,
    )


async def lock_row(conn, session_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow("select * from sessions where id = $1 for update", session_id)


async def get_row(conn, session_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow("select * from sessions where id = $1", session_id)


async def save_state(conn, session_id: str, state: dict, now: datetime, user_activity: bool, locked: bool) -> None:
    await conn.execute(
        "update sessions set state = $2, updated_at = $3, version = version + 1, locked = $5,"
        " last_user_activity_at = case when $4 then $3 else last_user_activity_at end"
        " where id = $1",
        session_id, state, now, user_activity, locked,
    )


async def insert_event(conn, session_id: str, now: datetime, kind: str, payload: dict) -> int:
    return await conn.fetchval(
        "insert into events (session_id, at, kind, payload) values ($1, $2, $3, $4) returning id",
        session_id, now, kind, payload,
    )


async def events_since(conn, session_id: str, after_id: int) -> list[tuple[int, str, dict]]:
    rows = await conn.fetch(
        "select id, kind, payload from events where session_id = $1 and id > $2 order by id",
        session_id, after_id,
    )
    return [(r["id"], r["kind"], r["payload"]) for r in rows]


async def count_created_since(conn, since: datetime, ip_hash: str | None = None) -> int:
    if ip_hash is None:
        return await conn.fetchval("select count(*) from sessions where created_at >= $1", since)
    return await conn.fetchval(
        "select count(*) from sessions where created_at >= $1 and ip_hash = $2", since, ip_hash)


async def set_call(conn, session_id: str, active: bool, now: datetime) -> None:
    await conn.execute(
        "update sessions set call_active = $2, call_seen_at = $3 where id = $1", session_id, active, now)


async def touch_call(conn, session_id: str, now: datetime, user_activity: bool) -> None:
    await conn.execute(
        "update sessions set call_seen_at = $2,"
        " last_user_activity_at = case when $3 then $2 else last_user_activity_at end where id = $1",
        session_id, now, user_activity)


async def mark_chat_connected(conn, session_id: str, now: datetime) -> bool:
    """Set chat_connected_at once. True the first time."""
    return await conn.fetchval(
        "update sessions set chat_connected_at = $2 where id = $1 and chat_connected_at is null returning true",
        session_id, now) is True


async def idle_candidates(conn, cutoff: datetime) -> list[str]:
    rows = await conn.fetch(
        "select id from sessions where not locked and not call_active and last_user_activity_at < $1", cutoff)
    return [r["id"] for r in rows]


async def chat_waiting(conn, cutoff: datetime) -> list[str]:
    rows = await conn.fetch(
        "select id from sessions where not locked and not call_active and chat_connected_at < $1"
        " and (state->>'calls')::int = 0 and state->'openCard' = 'null'::jsonb", cutoff)
    return [r["id"] for r in rows]


async def stale_calls(conn, cutoff: datetime) -> list[str]:
    rows = await conn.fetch(
        "select id from sessions where call_active and coalesce(call_seen_at, updated_at) < $1", cutoff)
    return [r["id"] for r in rows]

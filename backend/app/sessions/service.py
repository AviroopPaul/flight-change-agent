"""Session use cases. `apply` is the only way session state changes."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

import asyncpg

from app.core.result import Err, Ok
from app.records import service as records_service
from app.records.builder import build_record
from app.records.outcome import decide_outcome, is_final
from app.sessions import repository as repo
from app.sessions.models import Event, Result, SessionState, new_state
from app.telemetry import service as telemetry_service


@dataclass
class StoredEvent:
    id: int  # 0 for transient events that are not stored
    kind: str
    payload: dict


@dataclass
class ApplyOutcome:
    state: SessionState
    events: list[StoredEvent] = field(default_factory=list)
    reply: Ok | Err = field(default_factory=Ok)
    record: dict | None = None
    call_active: bool = False


class SessionNotFound(Exception):
    pass


def dump(state: SessionState) -> dict:
    return state.model_dump(by_alias=True, mode="json")


async def create_session(pool: asyncpg.Pool, ip_hash: str, now: datetime) -> str:
    sid = "s_" + secrets.token_hex(5)
    async with pool.acquire() as conn:
        await repo.insert_session(conn, sid, ip_hash, now, dump(new_state(sid)))
    return sid


async def load(pool: asyncpg.Pool, session_id: str) -> SessionState | None:
    async with pool.acquire() as conn:
        row = await repo.get_row(conn, session_id)
    return SessionState.model_validate(row["state"]) if row else None


async def get_row(pool: asyncpg.Pool, session_id: str):
    async with pool.acquire() as conn:
        return await repo.get_row(conn, session_id)


async def events_since(pool: asyncpg.Pool, session_id: str, after_id: int) -> list[tuple[int, str, dict]]:
    async with pool.acquire() as conn:
        return await repo.events_since(conn, session_id, after_id)


async def apply(
    pool: asyncpg.Pool,
    session_id: str,
    fn: Callable[[SessionState, bool], Result],
    *,
    now: datetime,
    user_activity: bool,
    idle: bool = False,
) -> ApplyOutcome:
    """Run one engine command in one transaction: lock, run, decide outcome, store events + record + state."""
    async with pool.acquire() as conn, conn.transaction():
        row = await repo.lock_row(conn, session_id)
        if row is None:
            raise SessionNotFound(session_id)
        call_active = row["call_active"]
        before = SessionState.model_validate(row["state"])
        result = fn(before, call_active)
        state = result.state
        events: list[Event] = list(result.events)
        record = None

        if not before.locked:
            if user_activity and state.last_outcome == "partial":
                state.last_outcome = None  # the user came back: reopen
            decided = decide_outcome(state, idle=idle)
            if decided is not None and decided[0] != state.last_outcome:
                outcome, reason = decided
                cost = await telemetry_service.session_cost(conn, session_id)
                record = build_record(state, outcome, reason, now=now, cost_usd=cost, ended_at=now)
                state.revision = record["revision"]
                state.last_outcome = outcome
                state.locked = is_final(outcome)
                if state.locked:
                    state.open_card = None
                events.append(Event("record", {"record": record}))
                await records_service.save_record(conn, session_id, record)

        stored: list[StoredEvent] = []
        for ev in events:
            eid = 0 if ev.kind in repo.TRANSIENT_KINDS else await repo.insert_event(
                conn, session_id, now, ev.kind, ev.payload)
            stored.append(StoredEvent(eid, ev.kind, ev.payload))
        await repo.save_state(conn, session_id, dump(state), now, user_activity, state.locked)
    return ApplyOutcome(state, stored, result.reply, record, call_active)

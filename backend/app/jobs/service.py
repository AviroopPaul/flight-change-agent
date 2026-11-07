"""The sweep: runs every 5 minutes (Cloud Scheduler) and once on startup."""

import logging
from datetime import datetime, timedelta

from fastapi import FastAPI

from app.sessions import engine
from app.sessions import service as sessions
from app.sessions.effects import after_apply, deliver_now

log = logging.getLogger("sweep")
IDLE_AFTER = timedelta(minutes=30)
STALE_CALL_AFTER = timedelta(minutes=15)
CHAT_AUTOSTART_AFTER = timedelta(seconds=20)


async def sweep(app: FastAPI, now: datetime) -> dict:
    pool = app.state.pool
    counts = {"closed": 0, "delivered": 0, "chatStarted": 0, "callsReset": 0}

    for sid in await sessions.stale_calls(pool, now - STALE_CALL_AFTER):
        out = await sessions.apply(pool, sid, lambda s, ca: engine.call_ended(s, 0, now), now=now,
                                   user_activity=False, set_call_active=False)
        after_apply(app, sid, out, origin="system", deliver=False)
        counts["callsReset"] += 1

    for sid in await sessions.idle_candidates(pool, now - IDLE_AFTER):
        state = await sessions.load(pool, sid)
        if state is None or state.locked or state.last_outcome == "partial":
            continue
        out = await sessions.apply(pool, sid, lambda s, ca: engine.identity(s), now=now, user_activity=False,
                                   idle=True)
        after_apply(app, sid, out, origin="system", deliver=False)
        if out.record is not None:
            counts["closed"] += 1

    for sid in await sessions.chat_waiting(pool, now - CHAT_AUTOSTART_AFTER):
        out = await sessions.apply(
            pool, sid, lambda s, ca: engine.identity(s) if ca else engine.advance(s, now, False),
            now=now, user_activity=False)
        after_apply(app, sid, out, origin="system", deliver=False)
        if any(e.kind == "inputRequest" for e in out.events):
            counts["chatStarted"] += 1

    counts["delivered"] = await deliver_now(app)
    if any(counts.values()):
        log.info("sweep %s", counts)
    return counts

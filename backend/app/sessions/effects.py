"""What happens after a state change is committed: push to chat, kick delivery."""

import logging

from fastapi import FastAPI

from app.core.tasks import spawn
from app.records.service import deliver_pending
from app.sessions.service import ApplyOutcome

log = logging.getLogger("effects")


async def deliver_now(app: FastAPI) -> int:
    s = app.state.settings
    return await deliver_pending(app.state.pool, app.state.http, s.effective_stub_url, s.service_token)


def after_apply(app: FastAPI, session_id: str, outcome: ApplyOutcome) -> None:
    hub = app.state.hub
    for ev in outcome.events:
        hub.publish(session_id, ev.id, ev.kind, ev.payload)
    if outcome.record is not None:
        spawn(app, deliver_now(app))

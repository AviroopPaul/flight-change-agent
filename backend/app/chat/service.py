"""Maps session events to starter wire messages, and client messages to engine commands."""

import asyncio


from fastapi import FastAPI

from app.core.clock import now_ist
from app.core.tasks import spawn
from app.sessions import engine
from app.sessions import service as sessions
from app.sessions.classify import classify_reason
from app.sessions.effects import after_apply
from app.sessions.models import Result, SessionState


def _with_id(msg: dict, eid: int) -> dict:
    if eid:
        msg["eventId"] = eid
    return msg


def live_message(eid: int, kind: str, payload: dict) -> dict | None:
    if kind == "message":
        return _with_id({"type": "message", "role": payload["role"], "text": payload["text"], "id": f"e{eid}"}, eid)
    if kind == "inputRequest":
        return _with_id({"type": "inputRequest", **payload}, eid)
    if kind == "inputError":
        return _with_id({"type": "inputError", "requestId": payload["requestId"], "message": payload["message"]}, eid)
    if kind == "inputCancel":
        return _with_id({"type": "inputCancel", **payload}, eid)
    if kind == "record":
        return _with_id({"type": "record", "record": payload["record"]}, eid)
    return None  # answer and fieldUpdate are not sent live (the page shows its own answers)


def replay_messages(state: SessionState, events: list[tuple[int, str, dict]]) -> list[dict]:
    answered = {p.get("requestId") for _, k, p in events if k == "answer"}
    open_ids = {state.open_card.id} if state.open_card else set()
    out = []
    for eid, kind, p in events:
        if kind == "inputRequest":
            if p["id"] in open_ids:
                out.append(_with_id({"type": "inputRequest", **p}, eid))
            elif p["id"] in answered:
                out.append(_with_id({"type": "message", "role": "agent", "text": p["label"], "id": f"e{eid}"}, eid))
        elif kind == "answer":
            out.append(_with_id({"type": "message", "role": "user", "text": str(p["value"]), "id": f"e{eid}"}, eid))
        elif kind in ("message", "record"):
            out.append(live_message(eid, kind, p))
    return out


async def _autostart(app: FastAPI, session_id: str) -> None:
    await asyncio.sleep(app.state.settings.chat_autostart_seconds)
    state = await sessions.load(app.state.pool, session_id)
    if state is None or state.calls > 0 or state.locked:
        return

    def start(s: SessionState, call_active: bool) -> Result:
        if call_active or s.calls > 0:
            return engine.identity(s)
        return engine.advance(s, now_ist(), False)

    after_apply(app, session_id, await sessions.apply(app.state.pool, session_id, start, now=now_ist(),
                                                      user_activity=False))


async def on_connect(app: FastAPI, session_id: str) -> None:
    pool = app.state.pool
    if await sessions.mark_chat_connected(pool, session_id, now_ist()):
        out = await sessions.apply(pool, session_id, lambda s, ca: engine.welcome(s), now=now_ist(),
                                   user_activity=False)
        after_apply(app, session_id, out)
        spawn(app, _autostart(app, session_id))


async def handle_client(app: FastAPI, session_id: str, msg: dict) -> list[dict]:
    """Apply one client message. Returns messages for this socket only."""
    pool = app.state.pool
    kind = msg.get("type")
    if kind == "optOut":
        out = await sessions.apply(pool, session_id, lambda s, ca: engine.ask_opt_out(s, now_ist()),
                                   now=now_ist(), user_activity=True)
        after_apply(app, session_id, out)
        return []
    if kind != "inputResponse":
        return []

    request_id, value = msg.get("requestId", ""), msg.get("value")
    state = await sessions.load(pool, session_id)
    category = None
    card = state.open_card if state else None
    if card and card.id == request_id and card.field == "changeReason" and card.purpose == "collect" and value:
        s = app.state.settings
        category = await classify_reason(str(value), s.groq_api_key, app.state.http)

    def answer(s: SessionState, call_active: bool) -> Result:
        r = engine.answer_card(s, request_id, value, now_ist(), call_active)
        if category and r.reply.ok and r.state.fields["changeReason"].status == "valid":
            c = engine.set_reason_category(r.state, category)
            return Result(c.state, r.events + c.events, r.reply)
        return r

    out = await sessions.apply(pool, session_id, answer, now=now_ist(), user_activity=True)
    after_apply(app, session_id, out)
    if not out.reply.ok and not any(e.kind == "inputError" for e in out.events):
        return [{"type": "inputError", "requestId": request_id, "message": out.reply.message}]
    return []




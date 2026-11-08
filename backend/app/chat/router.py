import asyncio
import contextlib
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.chat import service
from app.sessions import service as sessions
from app.sessions.engine import STALE
from app.telemetry import service as telemetry

router = APIRouter()


@router.websocket("/chat")
async def chat(ws: WebSocket, sessionId: str = "", after: int = 0):
    app = ws.app
    await ws.accept()
    if not sessionId or await sessions.load(app.state.pool, sessionId) is None:
        await ws.close(code=4404, reason="unknown session")
        return
    hub = app.state.hub
    queue = hub.subscribe(sessionId)
    sender = None
    try:
        await service.on_connect(app, sessionId)
        events = await sessions.events_since(app.state.pool, sessionId, after)
        state = await sessions.load(app.state.pool, sessionId)
        last = max([after] + [e[0] for e in events])
        # A fresh page has no thread, so it also gets the spoken call lines. A resume (after > 0)
        # already showed them live from the call.
        turns = await telemetry.all_turns(app.state.pool, sessionId) if after == 0 else []
        for m in service.replay_messages(state, events, turns):
            await ws.send_json(m)

        async def pump():
            while True:
                eid, kind, payload = await queue.get()
                if eid and eid <= last:
                    continue
                m = service.live_message(eid, kind, payload)
                if m is not None:
                    await ws.send_json(m)

        sender = asyncio.create_task(pump())
        while True:
            msg = await ws.receive_json()
            for m in await service.handle_client(app, sessionId, msg):
                await ws.send_json(m)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if sender:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await sender
        hub.unsubscribe(sessionId, queue)


# HTTP access for testing: the same answers as the chat socket, without a socket.

class AnswerIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    request_id: str | None = Field(default=None, alias="requestId")
    value: Any = None


def card_view(card) -> dict | None:
    return card.model_dump(by_alias=True, exclude_none=True) if card else None


def _view(state, **extra) -> dict:
    return {**extra, "openCard": card_view(state.open_card), "outcome": state.last_outcome, "locked": state.locked}


@router.post("/sessions/{session_id}/answers")
async def http_answer(session_id: str, body: AnswerIn, request: Request):
    """Answer the open chat card as the user. Without requestId, it answers the open card.
    With no card open and no call, it first greets and opens the next card, so a script needs no socket."""
    app = request.app
    state = await sessions.load(app.state.pool, session_id)
    if state is None:
        return JSONResponse({"ok": False, "error": "Session not found."}, status_code=404)
    if state.locked:
        return JSONResponse(_view(state, ok=False, error="This session is finished."), status_code=409)
    if state.open_card is None:
        state = await service.start_now(app, session_id)
    if state.open_card is None:
        return JSONResponse(_view(state, ok=False, error="No chat question is open."), status_code=409)
    out = await service.submit_answer(app, session_id, body.request_id or state.open_card.id, body.value)
    if out.reply.ok:
        return _view(out.state, ok=True)
    code = 409 if out.reply.message == STALE else 422
    return JSONResponse(_view(out.state, ok=False, error=out.reply.message), status_code=code)


@router.post("/sessions/{session_id}/stop")
async def http_stop(session_id: str, request: Request):
    """The chat's Stop button: opens the confirm card. Answer it with true to opt out."""
    state = await sessions.load(request.app.state.pool, session_id)
    if state is None:
        return JSONResponse({"ok": False, "error": "Session not found."}, status_code=404)
    if state.locked:
        return JSONResponse(_view(state, ok=False, error="This session is finished."), status_code=409)
    out = await service.stop(request.app, session_id)
    return _view(out.state, ok=True)

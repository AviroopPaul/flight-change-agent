import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.chat import service
from app.sessions import service as sessions
from app.telemetry import service as telemetry

router = APIRouter()


@router.websocket("/chat")
async def chat(ws: WebSocket, sessionId: str = "", after: int = 0):  # noqa: N803
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

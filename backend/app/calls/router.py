from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.calls import service
from app.calls.livekit import room_name
from app.calls.schemas import CallBody, CallToken, CategoryBody, FieldBody, FieldOnly, ResolveBody
from app.core.auth import require_service_token
from app.core.clock import now_ist
from app.core.http import parse_body
from app.sessions import engine
from app.sessions import service as sessions
from app.sessions.classify import classify_reason
from app.sessions.fields import ALL_FIELDS, CALL_NATIVE
from app.sessions.models import Result

MAX_ACTIVE_CALLS = 5
public = APIRouter()
internal = APIRouter(prefix="/internal/sessions/{session_id}", dependencies=[Depends(require_service_token)])
UNKNOWN_FIELD = {"ok": False, "error": "Unknown field."}


@public.post("/sessions/{session_id}/call-token")
async def call_token(session_id: str, request: Request):
    app = request.app
    row = await sessions.get_row(app.state.pool, session_id)
    if row is None:
        return JSONResponse({"error": "Session not found."}, status_code=404)
    if row["locked"]:
        return JSONResponse({"error": "This request is already submitted."}, status_code=409)
    if not row["call_active"] and await sessions.active_calls(app.state.pool) >= MAX_ACTIVE_CALLS:
        return JSONResponse({"error": "All agents are busy. Please use the chat or try again soon."},
                            status_code=429)
    lk = app.state.livekit
    await lk.ensure_dispatch(session_id)
    token = lk.mint_token(session_id, identity=f"user-{session_id}")
    return CallToken(token=token, url=app.state.settings.livekit_url, room=room_name(session_id)).model_dump()


@internal.get("/context")
async def context(session_id: str, request: Request):
    return await service.context(request.app, session_id)


@internal.post("/fields")
async def fields(session_id: str, request: Request):
    body = await parse_body(request, FieldBody)
    if isinstance(body, dict):
        return body
    if body.field not in ALL_FIELDS:
        return UNKNOWN_FIELD
    category = None
    if body.field == "changeReason" and body.value:
        st = request.app.state
        category = await classify_reason(str(body.value), st.settings.groq_api_key, st.http)

    def submit(s, ca):
        r = engine.submit_call_value(s, body.field, body.value, now_ist(), ca)
        if category and r.reply.ok and r.state.fields["changeReason"].status == "valid":
            c = engine.set_reason_category(r.state, category)
            return Result(c.state, r.events + c.events, r.reply)
        return r

    tool = "record_answer" if body.field in CALL_NATIVE else "note_spoken_value"
    return await service.run(request.app, session_id, submit, user_activity=True,
                             tool=tool, args={"field": body.field, "value": body.value})


@internal.post("/chat-input")
async def chat_input(session_id: str, request: Request):
    body = await parse_body(request, FieldOnly)
    if isinstance(body, dict):
        return body
    if body.field not in ALL_FIELDS:
        return UNKNOWN_FIELD
    return await service.run(request.app, session_id,
                             lambda s, ca: engine.request_chat_input(s, body.field, now_ist(), ca),
                             tool="send_chat_request", args={"field": body.field})


@internal.post("/conflicts/{field}/resolve")
async def resolve(session_id: str, field: str, request: Request):
    body = await parse_body(request, ResolveBody)
    if isinstance(body, dict):
        return body
    if field not in ALL_FIELDS:
        return UNKNOWN_FIELD
    return await service.run(request.app, session_id,
                             lambda s, ca: engine.resolve_conflict(s, field, body.choice, now_ist(), ca),
                             user_activity=True, tool="resolve_conflict", args={"field": field, "choice": body.choice})


@internal.post("/refund-instead")
async def refund_instead(session_id: str, request: Request):
    return await service.run(request.app, session_id,
                             lambda s, ca: engine.refund_instead(s, now_ist(), ca), user_activity=True,
                             tool="switch_to_refund")


@internal.post("/opt-out")
async def opt_out(session_id: str, request: Request):
    return await service.run(request.app, session_id, lambda s, ca: engine.opt_out(s, now_ist()),
                             user_activity=True, tool="stop_request")


@internal.post("/focus")
async def focus(session_id: str, request: Request):
    body = await parse_body(request, FieldOnly)
    if isinstance(body, dict):
        return body
    if body.field not in ALL_FIELDS:
        return UNKNOWN_FIELD
    return await service.run(request.app, session_id, lambda s, ca: engine.set_focus(s, body.field),
                             tool="set_focus", args={"field": body.field})


@internal.post("/reason-category")
async def reason_category(session_id: str, request: Request):
    body = await parse_body(request, CategoryBody)
    if isinstance(body, dict):
        return body
    return await service.run(request.app, session_id, lambda s, ca: engine.set_reason_category(s, body.category))


@internal.post("/call")
async def call(session_id: str, request: Request):
    body = await parse_body(request, CallBody)
    if isinstance(body, dict):
        return body
    if body.active:
        return await service.run(request.app, session_id, lambda s, ca: engine.call_started(s, now_ist()),
                                 set_call_active=True, tool="call", args={"active": True})
    return await service.run(request.app, session_id,
                             lambda s, ca: engine.call_ended(s, body.seconds, now_ist()), set_call_active=False,
                             tool="call", args={"active": False, "seconds": body.seconds})


router = APIRouter()
router.include_router(public)
router.include_router(internal)

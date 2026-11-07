from fastapi import APIRouter, Depends, Request

from app.core.auth import require_service_token
from app.core.clock import now_ist
from app.core.http import parse_body
from app.sessions import service as sessions
from app.telemetry import service
from app.telemetry.schemas import MetricsBody, TurnBody, UsageBody

router = APIRouter(prefix="/internal/sessions/{session_id}", dependencies=[Depends(require_service_token)])
UNKNOWN_SESSION = {"ok": False, "error": "Unknown session."}


async def _exists(request: Request, session_id: str) -> bool:
    return await sessions.get_row(request.app.state.pool, session_id) is not None


@router.post("/transcript")
async def transcript(session_id: str, request: Request):
    body = await parse_body(request, TurnBody)
    if isinstance(body, dict):
        return body
    if not await _exists(request, session_id):
        return UNKNOWN_SESSION
    pool = request.app.state.pool
    await service.add_turn(pool, session_id, body.role, body.text)
    await sessions.touch_call(pool, session_id, now_ist(), user_activity=body.role == "user")
    return {"ok": True}


@router.post("/usage")
async def usage(session_id: str, request: Request):
    body = await parse_body(request, UsageBody)
    if isinstance(body, dict):
        return body
    if body.kind not in service.USAGE_KINDS:
        return {"ok": False, "error": "Unknown usage kind."}
    if not await _exists(request, session_id):
        return UNKNOWN_SESSION
    await service.add_usage(request.app.state.pool, session_id, body.kind, body.quantity)
    return {"ok": True}


@router.post("/metrics")
async def metrics(session_id: str, request: Request):
    body = await parse_body(request, MetricsBody)
    if isinstance(body, dict):
        return body
    if not await _exists(request, session_id):
        return UNKNOWN_SESSION
    pool = request.app.state.pool
    await service.add_metrics(pool, session_id, body.eouMs, body.llmTtftMs, body.ttsTtfbMs)
    await sessions.touch_call(pool, session_id, now_ist(), user_activity=False)
    return {"ok": True}

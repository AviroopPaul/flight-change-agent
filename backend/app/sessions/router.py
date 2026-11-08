from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.clock import now_ist
from app.core.ratelimit import client_ip, ip_hash
from app.sessions import service
from app.sessions.schemas import SessionCreated, SessionView

router = APIRouter()


@router.post("/sessions")
async def create(request: Request):
    s = request.app.state.settings
    h = ip_hash(client_ip(request), s.service_token)
    try:
        sid = await service.create_session_limited(request.app.state.pool, h, now_ist(), s.daily_session_cap)
    except service.RateLimited:
        return JSONResponse({"error": "Too many sessions from this network. Try again later."}, status_code=429)
    except service.DailyCapReached:
        return JSONResponse({"error": "The demo is busy today. Please try again tomorrow."}, status_code=503)
    return SessionCreated(session_id=sid).model_dump(by_alias=True)


@router.get("/sessions/{session_id}")
async def get(session_id: str, request: Request):
    row = await service.get_row(request.app.state.pool, session_id)
    if row is None:
        return JSONResponse({"error": "Session not found."}, status_code=404)
    state = row["state"]
    return SessionView(session_id=session_id, locked=row["locked"], outcome=state.get("lastOutcome"),
                       call_active=row["call_active"], open_card=_open_card(state)).model_dump(by_alias=True)


def _open_card(state: dict) -> dict | None:
    card = state.get("openCard")
    return {k: v for k, v in card.items() if v is not None} if card else None

from fastapi import APIRouter, Depends, Request

from app.core.auth import require_service_token
from app.records import service

router = APIRouter()


@router.post("/stub/records", dependencies=[Depends(require_service_token)])
async def receive(request: Request):
    payload = await request.json()
    key = request.headers.get("idempotency-key") or f"{payload.get('sessionId')}:{payload.get('revision')}"
    stored = await service.stub_receive(request.app.state.pool, key, payload)
    return {"ok": True, "duplicate": not stored}


@router.get("/stub/records")
async def listing(request: Request, sessionId: str | None = None):  # noqa: N803
    """Without sessionId: keys and outcomes only. With it: that session's full records."""
    return {"records": await service.stub_list(request.app.state.pool, sessionId)}

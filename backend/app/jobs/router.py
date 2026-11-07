from fastapi import APIRouter, Depends, Request

from app.core.auth import require_service_token
from app.core.clock import now_ist
from app.jobs.service import sweep

router = APIRouter()


@router.post("/internal/sweep", dependencies=[Depends(require_service_token)])
async def run_sweep(request: Request):
    return await sweep(request.app, now_ist())

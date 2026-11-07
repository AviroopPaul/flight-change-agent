"""Helpers for the agent-facing API: every domain error is HTTP 200 with {ok:false, error}."""

from typing import TypeVar

from fastapi import Request
from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)
BAD_BODY = "I couldn't read that request."


async def parse_body(request: Request, model: type[M]) -> M | dict:
    """The parsed body, or an {ok:false} dict to return as-is."""
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        data = {}
    try:
        return model.model_validate(data)
    except ValidationError:
        return {"ok": False, "error": BAD_BODY}

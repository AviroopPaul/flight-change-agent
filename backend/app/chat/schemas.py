"""Starter chat wire messages (see web/src/protocol/types.ts)."""

from typing import Any, Literal

from pydantic import BaseModel


class InputResponse(BaseModel):
    type: Literal["inputResponse"]
    requestId: str  # noqa: N815
    field: str
    value: Any = None


class OptOut(BaseModel):
    type: Literal["optOut"]

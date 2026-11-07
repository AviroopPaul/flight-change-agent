from typing import Literal

from pydantic import BaseModel, Field


class TurnBody(BaseModel):
    role: Literal["user", "agent"]
    text: str = Field(max_length=4000)


class UsageBody(BaseModel):
    kind: str
    quantity: float = Field(ge=0)


class MetricsBody(BaseModel):
    eouMs: float = 0  # noqa: N815
    llmTtftMs: float = 0  # noqa: N815
    ttsTtfbMs: float = 0  # noqa: N815

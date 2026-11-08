from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from app.catalog.models import Quote
from app.core.model import CamelModel
from app.core.result import Err, Ok
from app.sessions.fields import ALL_FIELDS


class FieldState(CamelModel):
    value: Any = None
    source: Literal["call", "chat"] | None = None
    collected_at: datetime | None = None
    status: Literal["valid", "missing", "invalid"] = "missing"
    error: str | None = None
    attempts: int = 0


class Conflict(CamelModel):
    field: str
    call_value: Any = None
    chat_value: Any = None
    resolution: Literal["callValue", "chatValue"] | None = None
    reason: str | None = None


class InputCard(CamelModel):
    id: str
    field: str
    kind: str
    label: str
    help: str | None = None
    placeholder: str | None = None
    required: bool = True
    pattern: str | None = None
    options: list[dict] | None = None
    index: int | None = None
    purpose: Literal["collect", "conflict", "optOut"] = "collect"


class SessionState(CamelModel):
    session_id: str
    request_type: Literal["change", "refund"] = "change"
    fields: dict[str, FieldState]
    candidates: dict[str, dict[str, Any]] = {}
    conflicts: list[Conflict] = []
    open_card: InputCard | None = None
    card_seq: int = 0
    requested: list[str] = []
    quote: Quote | None = None
    offered_flight_ids: list[str] = []
    focus: str | None = None
    opted_out: bool = False
    revision: int = 0
    last_outcome: str | None = None
    locked: bool = False
    calls: int = 0
    call_seconds: int = 0
    call_started_at: datetime | None = None
    chat_messages: int = 0
    reason_category: str | None = None
    welcomed: bool = False


def new_state(session_id: str) -> SessionState:
    return SessionState(session_id=session_id, fields={f: FieldState() for f in ALL_FIELDS})


@dataclass
class Event:
    kind: str
    payload: dict


@dataclass
class Result:
    state: SessionState
    events: list[Event] = field(default_factory=list)
    reply: Ok | Err = field(default_factory=Ok)

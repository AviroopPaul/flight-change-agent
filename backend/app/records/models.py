from datetime import datetime
from typing import Any, Literal

from app.core.model import CamelModel

Outcome = Literal["completed", "partial", "optedOut", "needsReview"]


class RecordField(CamelModel):
    value: Any = None
    source: Literal["call", "chat"] | None = None
    collected_at: datetime | None = None
    status: Literal["valid", "missing", "invalid"] = "missing"


class RecordConflict(CamelModel):
    field: str
    call_value: Any = None
    chat_value: Any = None
    resolution: str | None = None
    reason: str | None = None


class Engagement(CamelModel):
    calls: int = 0
    call_seconds: int = 0
    chat_messages: int = 0


class BookingRef(CamelModel):
    pnr: str
    route: str
    original_flight: str
    original_departure: datetime
    fare_class: Literal["saver", "flex"]
    payment_method: str | None = None


class QuoteRef(CamelModel):
    id: str
    flight_id: str
    pax: int
    old_fare: int
    new_fare: int
    change_fee_per_pax: int
    net: int
    amount_due: int
    refund_due: int
    refund_to: str | None = None
    currency: Literal["INR"] = "INR"
    expires_at: datetime


class FinalRecord(CamelModel):
    """The one record a session produces per revision. Wire format is camelCase."""

    session_id: str
    revision: int
    request_type: Literal["change", "refund"]
    outcome: Outcome
    outcome_reason: str
    fields: dict[str, RecordField]
    conflicts: list[RecordConflict] = []
    booking: BookingRef | None = None
    quote: QuoteRef | None = None
    engagement: Engagement
    cost_usd: float
    ended_at: datetime


def record_json_schema() -> dict:
    return FinalRecord.model_json_schema(by_alias=True)

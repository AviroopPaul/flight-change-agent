"""Builds the final record from a session state. Pure."""

from datetime import datetime

from app.catalog.service import get_booking, get_flight
from app.records.models import BookingRef, Engagement, FinalRecord, QuoteRef, RecordConflict, RecordField
from app.sessions.fields import ALL_FIELDS
from app.sessions.models import SessionState


def _value(state: SessionState, name: str):
    f = state.fields[name]
    if f.status != "valid":
        return None
    if name == "changeReason":
        return {"text": f.value, "category": state.reason_category or "other"}
    if name == "selectedFlight":
        fl = get_flight(f.value)
        if fl is None:
            return {"flightId": f.value}
        return {"flightId": fl.id, "flightNo": fl.flight_no, "origin": fl.origin, "destination": fl.destination,
                "departure": fl.departure.isoformat(), "arrival": fl.arrival.isoformat(), "farePerPax": fl.fare}
    return f.value


def _call_seconds(state: SessionState, now: datetime) -> int:
    """Ended calls, plus the call still running when the record is built (else a mid-call record says 0)."""
    running = int((now - state.call_started_at).total_seconds()) if state.call_started_at else 0
    return state.call_seconds + max(0, running)


def build_record(state: SessionState, outcome: str, reason: str, *, now: datetime, cost_usd: float,
                 ended_at: datetime) -> dict:
    fields = {}
    for name in ALL_FIELDS:
        f = state.fields[name]
        valid = f.status == "valid"
        fields[name] = RecordField(value=_value(state, name), source=f.source if valid else None,
                                   collected_at=f.collected_at if valid else None,
                                   status="invalid" if f.status == "invalid" else f.status)

    booking = None
    if state.fields["pnr"].status == "valid":
        b = get_booking(state.fields["pnr"].value, now)
        if b is not None:
            booking = BookingRef(pnr=b.pnr, route=f"{b.origin}-{b.destination}", original_flight=b.flight_no,
                                 original_departure=b.departure, fare_class=b.fare_class,
                                 payment_method=b.payment_method)

    quote = None
    accepted = state.fields["fareAcceptance"].status == "valid" and (state.fields["fareAcceptance"].value or {}).get("accepted")
    if accepted and state.quote is not None and state.request_type == "change":
        q = state.quote
        quote = QuoteRef(id=q.id, flight_id=q.flight_id, pax=q.pax, old_fare=q.old_fare, new_fare=q.new_fare,
                         change_fee_per_pax=q.change_fee_per_pax, net=q.net, amount_due=q.amount_due,
                         refund_due=q.refund_due, refund_to=q.refund_to, expires_at=q.expires_at)

    record = FinalRecord(
        session_id=state.session_id,
        revision=state.revision + 1,
        request_type=state.request_type,
        outcome=outcome,
        outcome_reason=reason,
        fields=fields,
        conflicts=[RecordConflict.model_validate(c.model_dump()) for c in state.conflicts],
        booking=booking,
        quote=quote,
        engagement=Engagement(calls=state.calls, call_seconds=_call_seconds(state, now),
                              chat_messages=state.chat_messages),
        cost_usd=cost_usd,
        ended_at=ended_at,
    )
    return record.model_dump(by_alias=True, mode="json")

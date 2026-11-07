from datetime import datetime

from app.catalog.service import get_flight, load_bookings, make_quote
from app.core.clock import IST
from app.core.result import Ok
from app.sessions.models import FieldState, Result

NOW = datetime(2026, 11, 7, 10, 0, tzinfo=IST)


def complete(state, now=NOW):
    s = state.model_copy(deep=True)
    vals = dict(
        changeReason="meeting moved", newTravelDate="2026-12-13", timeFlexibility="any", pnr="ABC123",
        passengerNames=["RAHUL SHARMA"], contactEmail=None, selectedFlight="AQ101-20261213",
    )
    for k, v in vals.items():
        s.fields[k] = FieldState(value=v, source="chat", collected_at=now, status="valid")
    s.quote = make_quote(load_bookings(now)["ABC123"], get_flight("AQ101-20261213"), now)
    s.fields["fareAcceptance"] = FieldState(
        value={"accepted": True, "quoteId": s.quote.id, "amountDue": s.quote.amount_due, "currency": "INR"},
        source="chat", collected_at=now, status="valid")
    return s


def completing(state, call_active):
    return Result(complete(state), [], Ok())


def set_pnr(state, call_active):
    s = state.model_copy(deep=True)
    s.fields["pnr"] = FieldState(value="ABC123", source="chat", collected_at=NOW, status="valid")
    return Result(s, [], Ok())

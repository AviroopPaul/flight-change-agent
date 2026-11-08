import json
from datetime import datetime

from app.core.clock import IST
from app.records.builder import build_record
from app.records.models import FinalRecord
from app.records.outcome import decide_outcome, is_final
from app.sessions.models import Conflict, FieldState, new_state

NOW = datetime(2026, 11, 7, 10, 0, tzinfo=IST)
ALL_VALID = dict(
    changeReason="meeting moved", newTravelDate="2026-12-13", timeFlexibility="any", pnr="ABC123",
    passengerNames=["RAHUL SHARMA"], selectedFlight="AQ101-20261213",
    fareAcceptance={"accepted": True, "quoteId": "q_12345678", "amountDue": 3800, "currency": "INR"},
)


def state_with(**valid):
    s = new_state("s_test")
    for name, value in valid.items():
        s.fields[name] = FieldState(value=value, source="chat", collected_at=NOW, status="valid")
    return s


def completed_state():
    from app.catalog.service import get_flight, load_bookings, make_quote

    s = state_with(**ALL_VALID)
    s.quote = make_quote(load_bookings(NOW)["ABC123"], get_flight("AQ101-20261213"), NOW)
    s.reason_category = "schedule"
    return s


def test_precedence_optout_beats_completed():
    s = completed_state()
    s.opted_out = True
    assert decide_outcome(s, idle=False) == ("optedOut", "user asked to stop")


def test_refund_needs_review_without_flight():
    s = state_with(pnr="ABC123", passengerNames=["RAHUL SHARMA"], changeReason="sick")
    s.request_type = "refund"
    assert decide_outcome(s, idle=False) == ("needsReview", "refund requested instead of change")


def test_idle_with_conflict_is_needs_review_not_partial():
    s = state_with(pnr="ABC123")
    s.fields["newTravelDate"] = FieldState(status="invalid", error="conflict")
    s.conflicts.append(Conflict(field="newTravelDate", call_value="2026-12-14", chat_value="2026-12-13"))
    assert decide_outcome(s, idle=True) == ("needsReview", "unresolved conflict on newTravelDate")
    assert decide_outcome(s, idle=False) is None


def test_completed_requires_acceptance():
    assert decide_outcome(completed_state(), idle=False) == ("completed", "all required fields valid, fare accepted")
    s = completed_state()
    s.fields["fareAcceptance"] = FieldState()
    assert decide_outcome(s, idle=False) is None


def test_partial_reason_lists_missing():
    s = state_with(**{k: v for k, v in ALL_VALID.items() if k not in ("pnr", "selectedFlight", "fareAcceptance")})
    assert decide_outcome(s, idle=True) == (
        "partial", "user stopped responding with pnr, selectedFlight, fareAcceptance missing")


def test_not_idle_and_incomplete_returns_none():
    assert decide_outcome(new_state("s1"), idle=False) is None


def test_is_final():
    assert [is_final(o) for o in ("completed", "needsReview", "optedOut", "partial")] == [True, True, True, False]


def test_record_has_all_fields_and_iso_offsets():
    s = state_with(pnr="ABC123", changeReason="meeting moved")
    s.reason_category = "schedule"
    rec = build_record(s, "partial", "x", now=NOW, cost_usd=0.01, ended_at=NOW)
    assert set(rec["fields"]) == {"changeReason", "newTravelDate", "timeFlexibility", "pnr", "passengerNames",
                                  "selectedFlight", "fareAcceptance", "contactEmail"}
    for f in rec["fields"].values():
        if f["collectedAt"] is not None:
            assert f["collectedAt"].endswith("+05:30")
    assert rec["fields"]["contactEmail"] == {"value": None, "source": None, "collectedAt": None, "status": "missing"}
    assert rec["fields"]["changeReason"]["value"] == {"text": "meeting moved", "category": "schedule"}
    assert rec["endedAt"].endswith("+05:30")
    assert rec["booking"]["route"] == "BLR-DEL" and rec["booking"]["paymentMethod"] == "Visa •• 4242"
    assert "quote" not in rec or rec["quote"] is None
    FinalRecord.model_validate(rec)


def test_completed_record_has_quote_and_flight():
    rec = build_record(completed_state(), "completed", "ok", now=NOW, cost_usd=0.1, ended_at=NOW)
    assert rec["quote"]["amountDue"] == rec["quote"]["net"] > 0
    assert rec["quote"]["currency"] == "INR"
    assert rec["fields"]["selectedFlight"]["value"]["flightNo"] == "AQ101"
    assert rec["requestType"] == "change" and rec["outcome"] == "completed"
    assert rec["engagement"] == {"calls": 0, "callSeconds": 0, "chatMessages": 0}


def test_record_revision_increments():
    s = completed_state()
    assert build_record(s, "completed", "ok", now=NOW, cost_usd=0, ended_at=NOW)["revision"] == 1
    s.revision = 3
    assert build_record(s, "completed", "ok", now=NOW, cost_usd=0, ended_at=NOW)["revision"] == 4


def test_record_has_no_passenger_names_outside_fields():
    rec = build_record(completed_state(), "completed", "ok", now=NOW, cost_usd=0, ended_at=NOW)
    rest = dict(rec)
    rest["fields"] = {k: v for k, v in rec["fields"].items() if k != "passengerNames"}
    assert "RAHUL" not in json.dumps(rest, ensure_ascii=False).upper()


def test_json_schema_exports():
    schema = FinalRecord.model_json_schema(by_alias=True)
    assert "sessionId" in schema["properties"] and "costUsd" in schema["properties"]


def test_record_counts_time_of_a_call_still_running():
    """Live test: the record was built while the call was on and said callSeconds 0."""
    from datetime import timedelta
    s = completed_state()
    s.calls, s.call_seconds, s.call_started_at = 1, 30, NOW - timedelta(seconds=200)
    rec = build_record(s, "completed", "done", now=NOW, cost_usd=0.0, ended_at=NOW)
    assert rec["engagement"]["callSeconds"] == 230

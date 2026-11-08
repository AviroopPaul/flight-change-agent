from datetime import datetime, timedelta

import pytest

from app.core.clock import IST
from app.sessions import engine
from app.sessions.engine import (
    advance,
    answer_card,
    opt_out,
    refund_instead,
    request_chat_input,
    resolve_conflict,
    submit_call_value,
)
from app.sessions.models import FieldState, new_state

NOW = datetime(2026, 11, 7, 10, 0, tzinfo=IST)
STALE = "This question is no longer open."


def state_with(**valid):
    s = new_state("s_test")
    for name, value in valid.items():
        s.fields[name] = FieldState(value=value, source="chat", collected_at=NOW, status="valid")
    return s


def kinds(events):
    return [e.kind for e in events]


def cards(events):
    return [e.payload for e in events if e.kind == "inputRequest"]


def ready_for_flight():
    return state_with(
        pnr="ABC123", passengerNames=["RAHUL SHARMA"], contactEmail=None,
        changeReason="meeting moved", newTravelDate="2026-12-13", timeFlexibility="any",
    )


def at_fare_card():
    r = advance(ready_for_flight(), NOW, False)
    card = r.state.open_card
    assert card.field == "selectedFlight"
    r = answer_card(r.state, card.id, card.options[0]["value"], NOW, False)
    assert r.state.open_card.field == "fareAcceptance"
    return r


def test_first_card_after_call_is_pnr():
    r = advance(new_state("s1"), NOW, False)
    assert r.state.open_card.field == "pnr"
    assert r.state.open_card.pattern == "^[A-Za-z0-9]{6}$"
    assert r.state.open_card.label == "Booking reference (PNR)"
    assert kinds(r.events) == ["inputRequest"]


def test_one_card_at_a_time():
    r1 = request_chat_input(new_state("s1"), "pnr", NOW, True)
    r2 = request_chat_input(r1.state, "contactEmail", NOW, True)
    assert len(cards(r1.events) + cards(r2.events)) == 1
    pnr_card = r2.state.open_card
    r3 = answer_card(r2.state, pnr_card.id, "abc123", NOW, True)
    # One card at a time: the requested email comes first, then the names.
    assert [c["field"] for c in cards(r3.events)] == ["contactEmail"]
    assert r3.state.fields["pnr"].value == "ABC123"


def test_stale_request_id_rejected():
    r = advance(new_state("s1"), NOW, False)
    old = r.state.open_card.id
    r2 = answer_card(r.state, old, "ABC123", NOW, False)
    before = r2.state.model_dump()
    r3 = answer_card(r2.state, old, "ABC123", NOW, False)
    assert kinds(r3.events) == ["inputError"]
    assert r3.events[0].payload == {"requestId": old, "message": STALE}
    assert r3.state.model_dump() == before
    assert not r3.reply.ok


def test_passenger_cards_per_pax():
    r = advance(state_with(pnr="PQR456"), NOW, False)
    c1 = r.state.open_card
    assert c1.field == "passengerNames" and c1.label == "Passenger 1 of 2: full name as on ID"
    r = answer_card(r.state, c1.id, "Mrs Ananya Iyer", NOW, False)
    c2 = r.state.open_card
    assert c2.field == "passengerNames" and c2.index == 1 and c2.id != c1.id
    assert r.state.fields["passengerNames"].status == "missing"
    r = answer_card(r.state, c2.id, "kartik iyer", NOW, False)
    assert r.state.fields["passengerNames"].value == ["ANANYA IYER", "KARTIK IYER"]
    assert r.state.fields["passengerNames"].status == "valid"


def test_attempts_increment_on_error():
    r = advance(new_state("s1"), NOW, False)
    cid = r.state.open_card.id
    r = answer_card(r.state, cid, "ZZZ999", NOW, False)
    assert r.state.fields["pnr"].attempts == 1
    assert r.state.fields["pnr"].status == "invalid"
    assert r.events[0].payload == {
        "requestId": cid, "message": "I can't find a booking with that reference. Please check it.",
    }
    assert r.state.open_card.id == cid


def test_flight_card_waits_for_date_and_flex():
    s = state_with(pnr="ABC123", passengerNames=["RAHUL SHARMA"], contactEmail=None, changeReason="meeting")
    r = advance(s, NOW, False)
    assert r.state.open_card.field == "newTravelDate" and r.state.open_card.kind == "date"
    r = answer_card(r.state, r.state.open_card.id, "2026-12-13", NOW, False)
    assert r.state.open_card.field == "timeFlexibility" and r.state.open_card.kind == "select"
    r = answer_card(r.state, r.state.open_card.id, "afternoon", NOW, False)
    card = r.state.open_card
    assert card.field == "selectedFlight" and card.kind == "select"
    assert card.options and r.state.offered_flight_ids == [o["value"] for o in card.options]
    assert "you pay ₹" in card.options[0]["label"] or "refund ₹" in card.options[0]["label"]


def test_selected_flight_not_offered_is_rejected():
    r = advance(ready_for_flight(), NOW, False)
    r = answer_card(r.state, r.state.open_card.id, "AQ999-20261213", NOW, False)
    assert r.events[0].kind == "inputError"


def test_no_flights_message_and_date_invalid(monkeypatch):
    monkeypatch.setattr(engine, "flights_for", lambda *a, **k: [])
    r = advance(ready_for_flight(), NOW, False)
    msgs = [e.payload["text"] for e in r.events if e.kind == "message"]
    assert msgs == ["No seats match that date and time. Please pick another date or a wider time window."]
    assert r.state.fields["newTravelDate"].status == "invalid"
    assert r.state.open_card is None or r.state.open_card.field != "selectedFlight"
    assert all(c["field"] != "selectedFlight" for c in cards(r.events))


def test_date_change_cancels_open_flight_card():
    s = ready_for_flight()
    s.fields["newTravelDate"].source = "call"
    r = advance(s, NOW, False)
    old = r.state.open_card.id
    r = submit_call_value(r.state, "newTravelDate", "2026-12-20", NOW, True)
    cancels = [e.payload for e in r.events if e.kind == "inputCancel"]
    assert cancels and cancels[0]["requestId"] == old
    assert r.state.quote is None
    assert r.state.fields["selectedFlight"].status == "missing"
    new_cards = cards(r.events)
    assert new_cards and new_cards[0]["field"] == "selectedFlight"
    assert all(o["value"].endswith("20261220") for o in new_cards[0]["options"])


def test_fare_acceptance_breakdown_and_accept():
    r = at_fare_card()
    assert "Change fee ₹3,000" in r.state.open_card.label
    q = r.state.quote
    r = answer_card(r.state, r.state.open_card.id, True, NOW, False)
    v = r.state.fields["fareAcceptance"].value
    assert v["accepted"] is True and v["quoteId"] == q.id and v["currency"] == "INR"
    assert ("amountDue" in v) or ("refundDue" in v)


def test_decline_fare_reoffers_list():
    r = at_fare_card()
    r = answer_card(r.state, r.state.open_card.id, False, NOW, False)
    assert r.state.quote is None
    assert r.state.fields["selectedFlight"].status == "missing"
    assert r.state.open_card.field == "selectedFlight"


def test_expired_quote_requotes_on_accept():
    r = at_fare_card()
    old_id = r.state.quote.id
    later = NOW + timedelta(minutes=11)
    r2 = answer_card(r.state, r.state.open_card.id, True, later, False)
    assert r2.state.fields["fareAcceptance"].status == "valid"
    assert r2.state.fields["fareAcceptance"].value["quoteId"] != old_id

    s = r.state.model_copy(deep=True)
    s.quote.net += 500  # the stored quote no longer matches today's fare
    r3 = answer_card(s, s.open_card.id, True, later, False)
    assert r3.state.fields["fareAcceptance"].status != "valid"
    assert r3.state.open_card.field == "fareAcceptance" and r3.state.open_card.id != s.open_card.id


def test_spoken_pnr_then_typed_differs_auto_resolves_chat():
    r = submit_call_value(new_state("s1"), "pnr", "ABC 124", NOW, True)
    assert r.reply.ok and r.state.fields["pnr"].status == "missing"
    r = request_chat_input(r.state, "pnr", NOW, True)
    r = answer_card(r.state, r.state.open_card.id, "ABC123", NOW, True)
    assert r.state.fields["pnr"].value == "ABC123"
    [c] = r.state.conflicts
    assert c.field == "pnr" and c.resolution == "chatValue"
    assert c.reason == "typed value preferred over spoken"


def test_call_native_conflict_unresolved_marks_invalid():
    s = state_with(pnr="ABC123", newTravelDate="2026-12-13")
    r = submit_call_value(s, "newTravelDate", "2026-12-14", NOW, True)
    assert r.state.fields["newTravelDate"].status == "invalid"
    [c] = r.state.conflicts
    assert c.resolution is None and c.call_value == "2026-12-14" and c.chat_value == "2026-12-13"
    r = resolve_conflict(r.state, "newTravelDate", "chatValue", NOW)
    assert r.state.fields["newTravelDate"].status == "valid"
    assert r.state.fields["newTravelDate"].value == "2026-12-13"
    assert r.state.conflicts[0].resolution == "chatValue"


def test_date_conflict_cancels_open_flight_card():
    r = advance(ready_for_flight(), NOW, False)
    old = r.state.open_card.id
    r = submit_call_value(r.state, "newTravelDate", "2026-12-20", NOW, True)
    assert any(e.kind == "inputCancel" and e.payload["requestId"] == old for e in r.events)
    assert r.state.quote is None and r.state.conflicts[0].resolution is None


def test_conflict_card_offered_in_chat_when_no_call():
    s = state_with(pnr="ABC123", passengerNames=["RAHUL SHARMA"], contactEmail=None, newTravelDate="2026-12-13")
    r = submit_call_value(s, "newTravelDate", "2026-12-14", NOW, False)
    card = r.state.open_card
    assert card.purpose == "conflict" and card.kind == "select"
    assert [o["value"] for o in card.options] == ["callValue", "chatValue"]
    r = answer_card(r.state, card.id, "callValue", NOW, False)
    assert r.state.fields["newTravelDate"].value == "2026-12-14"


def test_refund_instead_skips_flight_and_cancels_card():
    r = advance(ready_for_flight(), NOW, False)
    old = r.state.open_card.id
    r = refund_instead(r.state, NOW)
    assert r.state.request_type == "refund"
    assert any(e.kind == "inputCancel" and e.payload["requestId"] == old for e in r.events)
    assert r.state.open_card is None


def test_email_skip_is_valid_none():
    r = advance(state_with(pnr="ABC123", passengerNames=["RAHUL SHARMA"]), NOW, False)
    card = r.state.open_card
    assert card.field == "contactEmail" and card.required is False
    r = answer_card(r.state, card.id, None, NOW, False)
    assert r.state.fields["contactEmail"].status == "valid"
    assert r.state.fields["contactEmail"].value is None


def test_opt_out_cancels_open_card():
    r = advance(new_state("s1"), NOW, False)
    r = opt_out(r.state, NOW)
    assert r.state.opted_out and r.state.open_card is None
    assert kinds(r.events)[0] == "inputCancel"


@pytest.mark.parametrize("call", [
    lambda s: submit_call_value(s, "changeReason", "meeting moved", NOW, True),
    lambda s: request_chat_input(s, "pnr", NOW, True),
    lambda s: answer_card(s, "r1", "ABC123", NOW, False),
    lambda s: refund_instead(s, NOW),
    lambda s: opt_out(s, NOW),
    lambda s: advance(s, NOW, False),
])
def test_locked_rejects_everything(call):
    s = new_state("s1")
    s.locked = True
    r = call(s)
    assert r.reply.ok is False and r.reply.message == "This request is already submitted."
    assert r.events == []


def test_unknown_field_is_err():
    r = submit_call_value(new_state("s1"), "shoeSize", "9", NOW, True)
    assert not r.reply.ok and r.reply.message == "Unknown field."


def test_chat_fields_continue_in_order_during_call():
    """A live call showed the agent never asked for names; the chat must keep going on its own."""
    r = request_chat_input(new_state("s1"), "pnr", NOW, True)
    r = answer_card(r.state, r.state.open_card.id, "ABC123", NOW, True)
    assert r.state.open_card is not None and r.state.open_card.field == "passengerNames"
    r = answer_card(r.state, r.state.open_card.id, "Rahul Sharma", NOW, True)
    assert r.state.open_card.field == "contactEmail"
    r = answer_card(r.state, r.state.open_card.id, None, NOW, True)
    assert r.state.open_card is None  # flights wait for the spoken date and time of day


def test_no_chat_card_during_call_before_agent_asks():
    r = advance(new_state("s1"), NOW, True)
    assert r.state.open_card is None


def test_spoken_date_reply_reads_back_weekday():
    r = submit_call_value(new_state("s1"), "newTravelDate", "2026-11-13", NOW, True)
    assert r.reply.ok and "Friday 13 November 2026" in r.reply.value
    upd = [e.payload for e in r.events if e.kind == "fieldUpdate"][0]
    assert upd["summary"] == "Friday 13 November 2026"
    assert r.state.fields["newTravelDate"].value == "2026-11-13"


def test_focus_follows_the_conversation():
    """The agent no longer spends an LLM round trip on set_focus; the engine tracks it."""
    r = submit_call_value(new_state("s1"), "changeReason", "meeting moved", NOW, True)
    assert r.state.focus == "newTravelDate"
    r = request_chat_input(r.state, "pnr", NOW, True)
    assert r.state.focus == "pnr"
    r = answer_card(r.state, r.state.open_card.id, "ABC123", NOW, True)
    assert r.state.focus == "passengerNames"


# ---------- every card blocks until it is answered, the optional email included ----------

def no_email_ready_for_flight():
    return state_with(pnr="ABC123", passengerNames=["RAHUL SHARMA"], changeReason="meeting moved",
                      newTravelDate="2026-12-13", timeFlexibility="any")


def test_optional_email_blocks_flights_until_answered():
    r = advance(no_email_ready_for_flight(), NOW, False)
    assert [c["field"] for c in cards(r.events)] == ["contactEmail"]
    assert r.state.open_card.required is False


def test_skipping_email_opens_flights():
    r = advance(no_email_ready_for_flight(), NOW, False)
    r = answer_card(r.state, r.state.open_card.id, None, NOW, False)
    assert r.state.fields["contactEmail"].status == "valid"
    assert [c["field"] for c in cards(r.events)] == ["selectedFlight"]


def test_typed_email_opens_flights():
    r = advance(no_email_ready_for_flight(), NOW, False)
    r = answer_card(r.state, r.state.open_card.id, "me@example.com", NOW, False)
    assert r.state.fields["contactEmail"].value == "me@example.com"
    assert r.state.open_card.field == "selectedFlight"


def test_spoken_answer_while_card_open_says_to_wait():
    """The agent must not move on while a chat card is open; the tool result tells it so."""
    r = request_chat_input(new_state("s1"), "pnr", NOW, True)
    r = submit_call_value(r.state, "newTravelDate", "2026-12-13", NOW, True)
    assert r.reply.ok
    assert "Booking reference (PNR)" in r.reply.value and "wait" in r.reply.value.lower()


def test_spoken_value_equal_to_typed_keeps_chat_source():
    """Live test: the date was picked in the chat, the agent saved the same date, and the record said 'call'."""
    s = state_with(newTravelDate="2026-12-13")
    r = submit_call_value(s, "newTravelDate", "2026-12-13", NOW, True)
    assert r.reply.ok
    assert r.state.fields["newTravelDate"].source == "chat"


def test_call_start_and_end_track_running_call():
    r = engine.call_started(new_state("s1"), NOW)
    assert r.state.call_started_at == NOW
    r = engine.call_ended(r.state, 90, NOW + timedelta(seconds=90))
    assert r.state.call_started_at is None and r.state.call_seconds == 90

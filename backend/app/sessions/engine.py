"""The conversation engine. Pure: every command takes a state and `now` and returns a Result.

No I/O and no clock. The caller (sessions.service.apply) persists the result.
"""

from datetime import date, datetime
from typing import Any, Literal

from app.catalog.service import WINDOWS, flights_for, get_booking, get_flight, load_bookings, make_quote
from app.core.result import Err, Ok
from app.sessions.fields import (
    ALL_FIELDS,
    CALL_NATIVE,
    CHAT_NATIVE,
    CHAT_ORDER,
    REASON_CATEGORIES,
    match_passenger,
    normalize_date,
    normalize_email,
    normalize_flex,
    normalize_name,
    normalize_pnr,
    normalize_reason,
)
from app.sessions.models import Conflict, Event, FieldState, InputCard, Result, SessionState

LOCKED = "This request is already submitted."
STALE = "This question is no longer open."
UNKNOWN = "Unknown field."
NO_FLIGHTS = "No seats match that date and time. Please pick another date or a wider time window."
PICK_LISTED = "Please pick one of the listed flights."
OPT_OUT_LABEL = "Stop this request? Nothing will be changed."
TYPED_WINS = "typed value preferred over spoken"
WELCOME = "Hi! I can help you change your flight. Tap the call button above to start, or answer the questions here."

FLIGHT_FIELDS = {"selectedFlight", "fareAcceptance"}
CALL_CHAT_ORDER = [*CHAT_ORDER[:3], "newTravelDate", *CHAT_ORDER[3:]]
REFUND_SKIPS = {"selectedFlight", "fareAcceptance", "contactEmail", "newTravelDate", "timeFlexibility"}
FLEX_LABELS = {
    "morning": "Morning (5 am to 12 pm)",
    "afternoon": "Afternoon (12 pm to 5 pm)",
    "evening": "Evening (5 pm to midnight)",
    "any": "Any time",
}
FIELD_LABELS = {
    "changeReason": "reason",
    "newTravelDate": "new travel date",
    "timeFlexibility": "time of day",
    "pnr": "booking reference",
    "passengerNames": "passenger names",
    "contactEmail": "email",
    "selectedFlight": "flight",
    "fareAcceptance": "fare",
}


# ---------- helpers ----------

def spoken_date(iso: str) -> str:
    """'2026-11-13' -> 'Friday 13 November 2026' (the agent reads this back instead of doing date math)."""
    return f"{date.fromisoformat(iso):%A %-d %B %Y}"


def rupees(n: int) -> str:
    return f"₹{n:,}"


def _start(state: SessionState) -> SessionState:
    return state.model_copy(deep=True)


def _locked(state: SessionState) -> Result:
    return Result(state, [], Err(LOCKED))


def _msg(text: str) -> Event:
    return Event("message", {"role": "agent", "text": text})


def _valid(state: SessionState, name: str) -> bool:
    return state.fields[name].status == "valid"


def _booking(state: SessionState, now: datetime):
    if not _valid(state, "pnr"):
        return None
    return get_booking(state.fields["pnr"].value, now)


def _summary(state: SessionState, name: str, now: datetime) -> str:
    f = state.fields[name]
    if f.status != "valid":
        return f.error or "missing"
    if name == "pnr":
        b = _booking(state, now)
        pax = len(b.passengers)
        return (f"Route {b.origin} to {b.destination} on {b.departure:%-d %b} at {b.departure:%H:%M}, "
                f"{pax} passenger{'s' if pax > 1 else ''}.")
    if name == "passengerNames":
        return f"All {len(f.value)} passenger names match."
    if name == "contactEmail":
        return "Skipped." if f.value is None else "Email saved."
    if name == "selectedFlight":
        fl = get_flight(f.value)
        q = state.quote
        return f"{fl.flight_no} on {fl.departure:%-d %b} at {fl.departure:%H:%M}. {_net_text(q.net) if q else ''}".strip()
    if name == "fareAcceptance":
        return "Fare accepted."
    if name == "changeReason":
        return f"Reason: {f.value}"
    if name == "newTravelDate":
        return spoken_date(f.value)
    return str(f.value)


def _update(state: SessionState, name: str, now: datetime) -> Event:
    return Event("fieldUpdate", {"field": name, "status": state.fields[name].status,
                                 "summary": _summary(state, name, now)})


def _set_valid(state: SessionState, name: str, value: Any, source: str, now: datetime) -> None:
    old = state.fields[name]
    state.fields[name] = FieldState(value=value, source=source, collected_at=now, status="valid",
                                    attempts=old.attempts)


def _set_error(state: SessionState, name: str, message: str) -> None:
    f = state.fields[name]
    f.attempts += 1
    if f.status != "valid":
        f.status = "invalid"
        f.error = message


def _cancel_open(state: SessionState, events: list[Event], reason: str, only: set[str] | None = None) -> str | None:
    card = state.open_card
    if card is None or (only is not None and card.field not in only):
        return None
    events.append(Event("inputCancel", {"requestId": card.id, "reason": reason}))
    state.open_card = None
    return card.field


def _clear_flight(state: SessionState, events: list[Event], reason: str) -> None:
    """Drop the offered list, the selection and the quote. Cancel an open flight or fare card."""
    had_flight = (_cancel_open(state, events, reason, only=FLIGHT_FIELDS) is not None
                  or state.quote is not None or bool(state.offered_flight_ids))
    state.quote = None
    state.offered_flight_ids = []
    state.fields["selectedFlight"] = FieldState()
    state.fields["fareAcceptance"] = FieldState()
    if had_flight and state.request_type == "change" and "selectedFlight" not in state.requested:
        state.requested.append("selectedFlight")


def _norm_for_compare(name: str, value: Any) -> Any:
    if value is None:
        return None
    if name == "pnr":
        return "".join(str(value).split()).upper()
    if name == "contactEmail":
        return str(value).strip().lower()
    if name == "passengerNames":
        vals = value if isinstance(value, list) else [value]
        return sorted(normalize_name(v) for v in vals)
    if name in ("timeFlexibility",):
        r = normalize_flex(value)
        return r.value if r.ok else str(value).strip().lower()
    return str(value).strip()


def _open_conflict(state: SessionState, name: str) -> Conflict | None:
    for c in state.conflicts:
        if c.field == name and c.resolution is None:
            return c
    return None


def _validate_call_native(state: SessionState, name: str, raw: Any, now: datetime) -> Ok | Err:
    if name == "changeReason":
        return normalize_reason(raw)
    if name == "newTravelDate":
        b = _booking(state, now)
        r = normalize_date(raw, now, b.departure if b else None)
        return Ok(r.value.isoformat()) if r.ok else r
    return normalize_flex(raw)


def _net_text(net: int) -> str:
    if net > 0:
        return f"you pay {rupees(net)}"
    if net < 0:
        return f"refund {rupees(-net)}"
    return "no extra cost"


def _quote_label(q, booking) -> str:
    pax = q.pax
    parts = [
        f"Old fare {rupees(q.old_fare)}/person.",
        f"New fare {rupees(q.new_fare)}/person.",
        f"Change fee {rupees(q.change_fee_per_pax)}/person.",
        f"{pax} passenger{'s' if pax > 1 else ''}.",
    ]
    if q.net > 0:
        parts.append(f"You pay {rupees(q.amount_due)}.")
    elif q.net < 0:
        parts.append(f"Refund {rupees(q.refund_due)} to {q.refund_to or 'your original payment method'}.")
    else:
        parts.append("Nothing to pay.")
    parts.append("Accept this change?")
    return " ".join(parts)


def _accept_value(q) -> dict:
    v: dict[str, Any] = {"accepted": True, "quoteId": q.id, "currency": "INR"}
    if q.net >= 0:
        v["amountDue"] = q.amount_due
    else:
        v["refundDue"] = q.refund_due
    return v


# ---------- card building ----------

def _applies(state: SessionState, name: str) -> bool:
    return not (state.request_type == "refund" and name in REFUND_SKIPS)


def _eligible(state: SessionState, name: str) -> bool:
    if name == "passengerNames":
        return _valid(state, "pnr")
    if name == "selectedFlight":
        return all(_valid(state, f) for f in ("pnr", "newTravelDate", "timeFlexibility"))
    if name == "fareAcceptance":
        return _valid(state, "selectedFlight") and state.quote is not None
    return True


def _next_id(state: SessionState) -> str:
    state.card_seq += 1
    return f"r{state.card_seq}"


def _build_card(state: SessionState, name: str, now: datetime, events: list[Event]) -> InputCard | None:
    cid = lambda: _next_id(state)  # noqa: E731
    if name == "pnr":
        return InputCard(id=cid(), field=name, kind="text", label="Booking reference (PNR)",
                         help="6 letters or digits, like ABC123.", placeholder="ABC123",
                         pattern="^[A-Za-z0-9]{6}$")
    if name == "passengerNames":
        b = _booking(state, now)
        done = state.fields[name].value or []
        i, n = len(done), len(b.passengers)
        return InputCard(id=cid(), field=name, kind="text", index=i,
                         label=f"Passenger {i + 1} of {n}: full name as on ID")
    if name == "contactEmail":
        return InputCard(id=cid(), field=name, kind="email", required=False,
                         label="Email for your new e-ticket (optional)", placeholder="you@example.com")
    if name == "changeReason":
        return InputCard(id=cid(), field=name, kind="text", label="Why do you want to change the flight?")
    if name == "newTravelDate":
        return InputCard(id=cid(), field=name, kind="date", label="New travel date")
    if name == "timeFlexibility":
        return InputCard(id=cid(), field=name, kind="select", label="What time of day suits you?",
                         options=[{"value": k, "label": v} for k, v in FLEX_LABELS.items()])
    if name == "selectedFlight":
        b = _booking(state, now)
        day = date.fromisoformat(state.fields["newTravelDate"].value)
        flights = [f for f in flights_for(b.origin, b.destination, day, state.fields["timeFlexibility"].value)
                   if f.departure > now]
        if not flights:
            events.append(_msg(NO_FLIGHTS))
            f = state.fields["newTravelDate"]
            f.status, f.error = "invalid", NO_FLIGHTS
            events.append(_update(state, "newTravelDate", now))
            return None
        options = []
        for fl in flights:
            q = make_quote(b, fl, now)
            label = (f"{fl.flight_no} · {fl.departure:%-d %b %H:%M} → {fl.arrival:%H:%M} · "
                     f"{rupees(fl.fare)}/person · {_net_text(q.net)}")
            options.append({"value": fl.id, "label": label})
        state.offered_flight_ids = [o["value"] for o in options]
        return InputCard(id=cid(), field=name, kind="select", label="Pick your new flight", options=options)
    if name == "fareAcceptance":
        return InputCard(id=cid(), field=name, kind="confirm", label=_quote_label(state.quote, _booking(state, now)))
    return None


def _conflict_card(state: SessionState, c: Conflict) -> InputCard:
    def show(v):
        return FLEX_LABELS.get(v, str(v)) if c.field == "timeFlexibility" else str(v)
    return InputCard(
        id=_next_id(state), field=c.field, kind="select", purpose="conflict",
        label=f"The call and the chat gave different {FIELD_LABELS[c.field]}s. Which is right?",
        options=[{"value": "callValue", "label": f"{show(c.call_value)} (said on the call)"},
                 {"value": "chatValue", "label": f"{show(c.chat_value)} (typed in chat)"}],
    )


def _candidates(state: SessionState, call_active: bool) -> list[str]:
    if call_active:
        # The agent starts the chat (usually with pnr). After that the typed fields follow in order on
        # their own, so a missed request (seen in a live call) can't leave a field unasked.
        # The date can be spoken or picked on a calendar, so its card follows the email in the chat.
        follow = [f for f in CALL_CHAT_ORDER if f not in state.requested] if _valid(state, "pnr") else []
        return list(state.requested) + follow
    return CHAT_ORDER + ["changeReason", "newTravelDate", "timeFlexibility"]


def _advance(state: SessionState, now: datetime, call_active: bool, events: list[Event]) -> None:
    _open_next(state, now, call_active, events)
    _track_focus(state)


def _track_focus(state: SessionState) -> None:
    """What the conversation is on now: the open chat box, else the next spoken field. Used to resume a call."""
    if state.open_card is not None:
        state.focus = state.open_card.field
        return
    spoken = ["changeReason", "newTravelDate", "timeFlexibility"]
    state.focus = next((f for f in spoken if _applies(state, f) and not _valid(state, f)), None)


def _open_next(state: SessionState, now: datetime, call_active: bool, events: list[Event]) -> None:
    if state.locked or state.opted_out or state.open_card is not None:
        return
    if not call_active:
        for c in state.conflicts:
            if c.resolution is None:
                state.open_card = _conflict_card(state, c)
                events.append(Event("inputRequest", _card_payload(state.open_card)))
                return
    for _ in range(len(ALL_FIELDS) + 2):  # a no-flights miss re-enters once
        picked = None
        for name in _candidates(state, call_active):
            if _valid(state, name) or not _applies(state, name) or not _eligible(state, name):
                continue
            if _open_conflict(state, name):
                continue
            picked = name
            break
        if picked is None:
            return
        card = _build_card(state, picked, now, events)
        if card is None:
            continue
        state.open_card = card
        events.append(Event("inputRequest", _card_payload(card)))
        return


def _card_payload(card: InputCard) -> dict:
    return card.model_dump(by_alias=True, exclude_none=True, mode="json")


def _done(state: SessionState, events: list[Event], reply: Ok | Err = Ok()) -> Result:
    return Result(state, events, reply)


# ---------- conflicts ----------

def _check_chat_native_conflict(state: SessionState, name: str, chat_value: Any) -> None:
    spoken = state.candidates.get(name, {}).get("call")
    if spoken is None:
        return
    if _norm_for_compare(name, spoken) != _norm_for_compare(name, chat_value):
        state.conflicts = [c for c in state.conflicts if c.field != name]
        state.conflicts.append(Conflict(field=name, call_value=spoken, chat_value=chat_value,
                                        resolution="chatValue", reason=TYPED_WINS))


# ---------- commands ----------

def advance(state: SessionState, now: datetime, call_active: bool) -> Result:
    if state.locked:
        return _locked(state)
    s = _start(state)
    events: list[Event] = []
    _advance(s, now, call_active, events)
    return _done(s, events)


def submit_call_value(state: SessionState, field: str, raw: Any, now: datetime, call_active: bool) -> Result:
    if state.locked:
        return _locked(state)
    if field not in ALL_FIELDS:
        return Result(state, [], Err(UNKNOWN))
    s = _start(state)
    events: list[Event] = []

    if field in CHAT_NATIVE:
        s.candidates.setdefault(field, {})["call"] = raw
        f = s.fields[field]
        if f.status == "valid" and f.source == "chat":
            _check_chat_native_conflict(s, field, f.value)
        return _done(s, events, Ok("Noted. Ask the user to type it in the chat, where it will be checked."))

    r = _validate_call_native(s, field, raw, now)
    if not r.ok:
        _set_error(s, field, r.message)
        events.append(_update(s, field, now))
        return _done(s, events, r)

    value = r.value
    f = s.fields[field]
    existing = _open_conflict(s, field)
    if existing is not None:
        existing.call_value = value
        events.append(_update(s, field, now))
        return _done(s, events, Err(_conflict_prompt(existing)))
    if f.status == "valid" and f.source == "chat" and _norm_for_compare(field, f.value) != _norm_for_compare(field, value):
        c = Conflict(field=field, call_value=value, chat_value=f.value)
        s.conflicts.append(c)
        f.status, f.error = "invalid", "conflict"
        if field in ("newTravelDate", "timeFlexibility"):
            _clear_flight(s, events, "The date or time is being checked.")
        events.append(_update(s, field, now))
        _advance(s, now, call_active, events)
        return _done(s, events, Err(_conflict_prompt(c)))

    if f.status == "valid" and f.source == "chat" and _norm_for_compare(field, f.value) == _norm_for_compare(field, value):
        if field == "newTravelDate":
            return _done(s, events, Ok(f"Already saved from the chat: {spoken_date(value)}."))
        return _done(s, events, Ok(f"Already saved from the chat: {f.value}."))
    changed = f.status == "valid" and f.value != value
    _set_valid(s, field, value, "call", now)
    _cancel_open(s, events, "Answered on the call.", only={field})
    if field in ("newTravelDate", "timeFlexibility") and changed:
        _clear_flight(s, events, "The date or time changed.")
    events.append(_update(s, field, now))
    _advance(s, now, call_active, events)
    if field == "newTravelDate":
        return _done(s, events, Ok(f"Saved {spoken_date(value)}. Read this date back to the caller exactly."
                                   f"{_wait_hint(s)}"))
    hint = _wait_hint(s)
    return _done(s, events, Ok(f"{value}.{hint}" if hint else value))


def _wait_hint(s: SessionState) -> str:
    """While a chat card is open, the agent asks nothing new: one input at a time."""
    card = s.open_card
    if card is None or card.purpose != "collect":
        return ""
    if card.field == "newTravelDate":
        return " A calendar for the new travel date is open in the chat. The caller can say the date or pick it there."
    return (f" A chat box is open for: {card.label}. Remind the caller to finish it in the chat, then wait. "
            "Ask no new question until it is submitted.")


def _conflict_prompt(c: Conflict) -> str:
    return (f"The chat says {c.chat_value} but the call says {c.call_value} for the {FIELD_LABELS[c.field]}. "
            "Ask the user which is right, then call resolve_conflict.")


def request_chat_input(state: SessionState, field: str, now: datetime, call_active: bool) -> Result:
    if state.locked:
        return _locked(state)
    if field not in ALL_FIELDS:
        return Result(state, [], Err(UNKNOWN))
    if state.fields[field].status == "valid":
        return Result(state, [], Err(f"The {FIELD_LABELS[field]} is already filled in."))
    if not _applies(state, field):
        return Result(state, [], Err(f"The {FIELD_LABELS[field]} is not needed for a refund."))
    s = _start(state)
    events: list[Event] = []
    if field not in s.requested:
        s.requested.append(field)
    _advance(s, now, call_active, events)
    if s.open_card is not None and s.open_card.field == field:
        reply = Ok("Sent to the chat.")
    elif not _eligible(s, field):
        reply = Ok("Queued. It will show in the chat once the booking reference, date and time of day are set.")
    else:
        reply = Ok("Queued. It will show in the chat after the current question.")
    return _done(s, events, reply)


def answer_card(state: SessionState, request_id: str, value: Any, now: datetime, call_active: bool) -> Result:
    if state.locked:
        return _locked(state)
    card = state.open_card
    if card is None or card.id != request_id:
        return Result(state, [Event("inputError", {"requestId": request_id, "message": STALE})], Err(STALE))
    s = _start(state)
    events: list[Event] = []

    if card.purpose == "optOut":
        s.open_card = None
        if value is True:
            events.append(Event("answer", {"requestId": card.id, "field": "__optOut", "value": "Yes, stop"}))
            return _opt_out(s, events)
        events.append(Event("answer", {"requestId": card.id, "field": "__optOut", "value": "No, continue"}))
        events.append(_msg("Okay, let's carry on."))
        _advance(s, now, call_active, events)
        return _done(s, events)

    if card.purpose == "conflict":
        if value not in ("callValue", "chatValue"):
            events.append(Event("inputError", {"requestId": card.id, "message": "Please pick one of the options."}))
            return _done(s, events, Err("Please pick one of the options."))
        s.open_card = None
        label = next((o["label"] for o in card.options or [] if o["value"] == value), value)
        events.append(Event("answer", {"requestId": card.id, "field": card.field, "value": label}))
        s.chat_messages += 1
        _resolve(s, card.field, value, now, events)
        _advance(s, now, call_active, events)
        return _done(s, events)

    name = card.field
    r = _validate_answer(s, card, value, now)
    if not r.ok:
        _set_error(s, name, r.message)
        events.append(Event("inputError", {"requestId": card.id, "message": r.message}))
        return _done(s, events, r)

    s.chat_messages += 1
    s.open_card = None
    events.append(Event("answer", {"requestId": card.id, "field": name, "value": _display(card, value)}))

    if name == "passengerNames":
        f = s.fields[name]
        names = list(f.value or []) + [r.value]
        b = _booking(s, now)
        if len(names) < len(b.passengers):
            f.value, f.source, f.collected_at, f.status, f.error = names, "chat", now, "missing", None
            s.open_card = _build_card(s, name, now, events)
            events.append(Event("inputRequest", _card_payload(s.open_card)))
            return _done(s, events)
        _set_valid(s, name, names, "chat", now)
        _check_chat_native_conflict(s, name, names)
    elif name == "fareAcceptance":
        return _answer_fare(s, value, now, call_active, events)
    elif name in CALL_NATIVE:
        f = s.fields[name]
        changed = f.status == "valid" and f.value != r.value
        _set_valid(s, name, r.value, "chat", now)
        if name in ("newTravelDate", "timeFlexibility") and changed:
            _clear_flight(s, events, "The date or time changed.")
    else:
        if name == "pnr" and _valid(s, "pnr") and s.fields["pnr"].value != r.value:
            s.fields["passengerNames"] = FieldState()
            _clear_flight(s, events, "The booking changed.")
        _set_valid(s, name, r.value, "chat", now)
        if name == "selectedFlight":
            s.quote = make_quote(_booking(s, now), get_flight(r.value), now)
        _check_chat_native_conflict(s, name, r.value)

    if name in s.requested and _valid(s, name):
        s.requested.remove(name)
    if name == "selectedFlight" and "fareAcceptance" not in s.requested and call_active:
        s.requested.append("fareAcceptance")
    events.append(_update(s, name, now))
    _advance(s, now, call_active, events)
    return _done(s, events)


def _display(card: InputCard, value: Any) -> str:
    if value is None:
        return "(skipped)"
    if card.kind == "confirm":
        return "Yes" if value is True else "No"
    for o in card.options or []:
        if o["value"] == value:
            return o.get("label") or str(value)
    return str(value)


def _validate_answer(s: SessionState, card: InputCard, value: Any, now: datetime) -> Ok | Err:
    name = card.field
    if name == "pnr":
        return normalize_pnr(value, load_bookings(now), now)
    if name == "passengerNames":
        return match_passenger(value, _booking(s, now), list(s.fields[name].value or []))
    if name == "contactEmail":
        return Ok(None) if value in (None, "") else normalize_email(value)
    if name == "selectedFlight":
        return Ok(value) if value in s.offered_flight_ids else Err(PICK_LISTED)
    if name == "fareAcceptance":
        return Ok(value) if isinstance(value, bool) else Err("Please answer yes or no.")
    if name in CALL_NATIVE:
        return _validate_call_native(s, name, value, now)
    return Err(UNKNOWN)


def _answer_fare(s: SessionState, value: bool, now: datetime, call_active: bool, events: list[Event]) -> Result:
    if value is False:
        _clear_flight(s, events, "Fare declined.")
        events.append(_msg("No problem. Here are the flights again. You can also pick a different date."))
        events.append(_update(s, "fareAcceptance", now))
        _advance(s, now, call_active, events)
        return _done(s, events)
    q = s.quote
    if now >= q.expires_at:
        fresh = make_quote(_booking(s, now), get_flight(s.fields["selectedFlight"].value), now)
        s.quote = fresh
        if fresh.net != q.net:
            events.append(_msg("The fare changed since the quote. Please check the new total."))
            if "fareAcceptance" not in s.requested and call_active:
                s.requested.append("fareAcceptance")
            _advance(s, now, call_active, events)
            return _done(s, events)
        q = fresh
    _set_valid(s, "fareAcceptance", _accept_value(q), "chat", now)
    if "fareAcceptance" in s.requested:
        s.requested.remove("fareAcceptance")
    events.append(_update(s, "fareAcceptance", now))
    _advance(s, now, call_active, events)
    return _done(s, events)


def _resolve(s: SessionState, field: str, choice: str, now: datetime, events: list[Event]) -> Ok | Err:
    c = _open_conflict(s, field)
    if c is None:
        return Err("There is no open conflict on that field.")
    c.resolution = choice
    c.reason = "confirmed by the user"
    value = c.call_value if choice == "callValue" else c.chat_value
    source = "call" if choice == "callValue" else "chat"
    before = s.fields[field].value
    _set_valid(s, field, value, source, now)
    if field in ("newTravelDate", "timeFlexibility") and before != value:
        _clear_flight(s, events, "The date or time changed.")
    events.append(_update(s, field, now))
    return Ok(value)


def resolve_conflict(state: SessionState, field: str, choice: Literal["callValue", "chatValue"],
                     now: datetime, call_active: bool = False) -> Result:
    if state.locked:
        return _locked(state)
    if field not in ALL_FIELDS:
        return Result(state, [], Err(UNKNOWN))
    if choice not in ("callValue", "chatValue"):
        return Result(state, [], Err("Choice must be callValue or chatValue."))
    s = _start(state)
    events: list[Event] = []
    r = _resolve(s, field, choice, now, events)
    if not r.ok:
        return Result(state, [], r)
    if s.open_card is not None and s.open_card.purpose == "conflict" and s.open_card.field == field:
        _cancel_open(s, events, "Resolved on the call.")
    _advance(s, now, call_active, events)
    return _done(s, events, r)


def refund_instead(state: SessionState, now: datetime, call_active: bool = False) -> Result:
    if state.locked:
        return _locked(state)
    s = _start(state)
    events: list[Event] = []
    s.request_type = "refund"
    _cancel_open(s, events, "Switched to a refund.", only=REFUND_SKIPS)
    s.quote = None
    s.offered_flight_ids = []
    s.fields["selectedFlight"] = FieldState()
    s.fields["fareAcceptance"] = FieldState()
    s.requested = [f for f in s.requested if f not in REFUND_SKIPS]
    events.append(_msg("Okay, we'll treat this as a refund request. A person will review it."))
    _advance(s, now, call_active, events)
    return _done(s, events, Ok(_refund_reply(s)))


def _refund_reply(s: SessionState) -> str:
    """Tell the agent the request is not done yet, so it does not say goodbye early."""
    missing = [FIELD_LABELS[f] for f in ALL_FIELDS if _applies(s, f) and not _valid(s, f)]
    if not missing:
        return "Switched to a refund request."
    return (f"Switched to a refund request. It is not finished: a person needs the {', '.join(missing)} first. "
            "Do not say goodbye yet." + _wait_hint(s))


def _opt_out(s: SessionState, events: list[Event]) -> Result:
    s.opted_out = True
    _cancel_open(s, events, "Request stopped.")
    s.requested = []
    events.append(_msg("Okay, I've stopped this request. Nothing has been changed."))
    return _done(s, events, Ok("Stopped."))


def opt_out(state: SessionState, now: datetime) -> Result:
    if state.locked:
        return _locked(state)
    s = _start(state)
    return _opt_out(s, [])


def ask_opt_out(state: SessionState, now: datetime) -> Result:
    """The chat's Stop button: put a confirm card in front of everything else."""
    if state.locked:
        return _locked(state)
    s = _start(state)
    events: list[Event] = []
    if s.open_card is not None and s.open_card.purpose == "optOut":
        return _done(s, events)
    _cancel_open(s, events, "Paused while you decide.")
    s.open_card = InputCard(id=_next_id(s), field="__optOut", kind="confirm", label=OPT_OUT_LABEL,
                            purpose="optOut")
    events.append(Event("inputRequest", _card_payload(s.open_card)))
    return _done(s, events)


def set_focus(state: SessionState, field: str) -> Result:
    if state.locked:
        return _locked(state)
    if field not in ALL_FIELDS:
        return Result(state, [], Err(UNKNOWN))
    s = _start(state)
    s.focus = field
    return _done(s, [])


def set_reason_category(state: SessionState, category: str) -> Result:
    if state.locked:
        return _locked(state)
    s = _start(state)
    s.reason_category = category if category in REASON_CATEGORIES else "other"
    return _done(s, [], Ok(s.reason_category))


def identity(state: SessionState) -> Result:
    return Result(_start(state), [], Ok())


def welcome(state: SessionState) -> Result:
    """The first chat connect: greet once."""
    if state.locked:
        return _locked(state)
    s = _start(state)
    if s.welcomed:
        return _done(s, [])
    s.welcomed = True
    return _done(s, [_msg(WELCOME)])


def call_started(state: SessionState, now: datetime | None = None) -> Result:
    s = _start(state)
    if not s.locked:
        s.calls += 1
    s.call_started_at = now
    return _done(s, [])


def call_ended(state: SessionState, seconds: int, now: datetime) -> Result:
    """The call is over: count its time and let the chat take over."""
    s = _start(state)
    s.call_seconds += max(0, int(seconds))
    s.call_started_at = None
    events: list[Event] = []
    if not s.locked:
        s.requested = []
        _advance(s, now, False, events)
    return _done(s, events)

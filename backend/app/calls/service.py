"""Use cases for the voice agent: context to (re)build its prompt, and commands it runs."""

from collections.abc import Callable

from fastapi import FastAPI

from app.catalog.service import get_booking
from app.core.clock import now_ist
from app.sessions import service as sessions
from app.sessions.effects import after_apply, record_summary
from app.sessions.models import Result, SessionState
from app.telemetry import service as telemetry

UNKNOWN_SESSION = {"ok": False, "error": "Unknown session."}


def _field_view(state: SessionState) -> dict:
    out = {}
    for name, f in state.fields.items():
        value = f.value
        if name == "passengerNames":
            value = len(f.value) if isinstance(f.value, list) else None  # never names
        out[name] = {"status": f.status, "value": value, "source": f.source, "error": f.error,
                     "attempts": f.attempts}
    return out


def state_view(state: SessionState) -> dict:
    """The agent's view of the state. No passenger names, no spoken candidates."""
    return {
        "requestType": state.request_type,
        "fields": _field_view(state),
        "openConflicts": [{"field": c.field, "callValue": c.call_value, "chatValue": c.chat_value}
                          for c in state.conflicts if c.resolution is None and c.field != "passengerNames"],
        "locked": state.locked,
        "outcome": state.last_outcome,
        "calls": state.calls,
        "callSeconds": state.call_seconds,
        "reasonCategory": state.reason_category,
    }


def booking_summary(state: SessionState, now) -> dict | None:
    if state.fields["pnr"].status != "valid":
        return None
    b = get_booking(state.fields["pnr"].value, now)
    if b is None:
        return None
    return {"route": f"{b.origin}-{b.destination}", "from": b.origin, "to": b.destination,
            "date": b.departure.date().isoformat(), "time": b.departure.strftime("%H:%M"),
            "pax": len(b.passengers), "fareClass": b.fare_class}


async def context(app: FastAPI, session_id: str) -> dict:
    pool = app.state.pool
    state = await sessions.load(pool, session_id)
    if state is None:
        return UNKNOWN_SESSION
    now = now_ist()
    card = state.open_card.model_dump(by_alias=True, exclude_none=True, mode="json") if state.open_card else None
    return {
        "ok": True,
        "state": state_view(state),
        "openCard": card,
        "focus": state.focus,
        "transcript": await telemetry.last_turns(pool, session_id, 20),
        "today": now.date().isoformat(),
        "weekday": now.strftime("%A"),
        "bookingSummary": booking_summary(state, now),
    }


async def run(app: FastAPI, session_id: str, fn: Callable[[SessionState, bool], Result], *,
              user_activity: bool = False, set_call_active: bool | None = None) -> dict:
    """Apply an agent command and turn the reply into {ok, result | error} for the LLM tool."""
    try:
        out = await sessions.apply(app.state.pool, session_id, fn, now=now_ist(), user_activity=user_activity,
                                   set_call_active=set_call_active)
    except sessions.SessionNotFound:
        return UNKNOWN_SESSION
    after_apply(app, session_id, out, origin="agent")
    resp: dict = {"ok": True, "result": out.reply.value} if out.reply.ok else {"ok": False, "error": out.reply.message}
    if out.record is not None:
        resp["outcome"] = out.record["outcome"]
        resp["summary"] = record_summary(out.record)
    return resp

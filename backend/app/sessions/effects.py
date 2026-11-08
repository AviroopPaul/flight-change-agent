"""What happens after a state change is committed: push to chat, kick delivery."""

import logging

from fastapi import FastAPI

from app.sessions.engine import spoken_date
from app.core.tasks import spawn
from app.records.service import deliver_pending
from app.sessions.service import ApplyOutcome

log = logging.getLogger("effects")


async def deliver_now(app: FastAPI) -> int:
    s = app.state.settings
    return await deliver_pending(app.state.pool, app.state.http, s.effective_stub_url, s.service_token)


CALL_KINDS = {"fieldUpdate", "answer", "message"}


def call_events(events: list, state) -> list[tuple[str, dict]]:
    """Chat events for the call agent. The last fieldUpdate also says which chat box is open now, so the agent
    knows whether to wait (one input at a time) or to ask its next spoken question."""
    out = [(ev.kind, dict(ev.payload)) for ev in events if ev.kind in CALL_KINDS]
    last = max((i for i, (k, _) in enumerate(out) if k == "fieldUpdate"), default=None)
    if last is not None:
        card = state.open_card
        out[last][1]["openCard"] = None if card is None else {
            "field": card.field, "label": card.label, "optional": card.required is False}
    return out


def record_summary(record: dict) -> str:
    """What the agent says when the session ends during a call (spec section 9)."""
    outcome = record["outcome"]
    if outcome == "completed":
        fl = record["fields"]["selectedFlight"]["value"] or {}
        q = record.get("quote") or {}
        dep = fl.get("departure", "")
        when = f"{spoken_date(dep[:10])} at {dep[11:16]}" if len(dep) >= 16 else dep
        if q.get("amountDue"):
            money = f"You pay {q['amountDue']:,} rupees."
        elif q.get("refundDue"):
            money = f"A refund of {q['refundDue']:,} rupees goes back to {q.get('refundTo') or 'your original payment'}."
        else:
            money = "There is nothing to pay."
        return f"You're all set. Your new flight is {fl.get('flightNo', '')} on {when}. {money}"
    if outcome == "needsReview":
        if record.get("requestType") == "refund":
            return "Thanks. A person will process your refund and get back to you."
        return "Thanks. A person will review your request and get back to you."
    if outcome == "optedOut":
        return "Okay, I've stopped your request. Nothing has been changed."
    return "I've saved your progress. You can finish in the chat."


def after_apply(app: FastAPI, session_id: str, outcome: ApplyOutcome, origin: str = "chat",
                deliver: bool = True) -> None:
    """origin: "chat", "agent" or "system". The agent already knows what its own tools did."""
    hub = app.state.hub
    for ev in outcome.events:
        hub.publish(session_id, ev.id, ev.kind, ev.payload)
    if outcome.record is not None and deliver:
        spawn(app, deliver_now(app))
    if outcome.call_active and origin != "agent":
        lk = app.state.livekit
        for kind, payload in call_events(outcome.events, outcome.state):
            spawn(app, lk.send_event(session_id, kind, payload))
        if outcome.record is not None:
            spawn(app, lk.send_event(session_id, "outcome", {
                "outcome": outcome.record["outcome"], "summary": record_summary(outcome.record)}))

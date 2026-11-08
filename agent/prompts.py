"""Prompt text. Spoken through TTS, so no em dashes and short sentences."""

import re
from datetime import date, timedelta

_DASH = re.compile(r"\s*[\u2014\u2013]\s*")


def clean_text(text: str) -> str:
    """No em or en dashes in anything the agent says (copy rule)."""
    return _DASH.sub(", ", text)

GREETING = "Hi, I can help you change your flight. What's the reason for the change?"
TIME_LIMIT = "We're at the time limit for this call. You can finish in the chat."

QUESTIONS = {
    "changeReason": "What's the reason for the change?",
    "newTravelDate": "What date would you like to fly instead?",
    "timeFlexibility": "What time of day suits you: morning, afternoon, evening, or any time?",
    "pnr": "Could you type your booking reference in the box in the chat?",
    "passengerNames": "Could you type the passenger names in the chat, as on the ID?",
    "contactEmail": "You can add an email for the new e-ticket in the chat, or skip it.",
    "selectedFlight": "Please pick a flight from the list in the chat.",
    "fareAcceptance": "Please check the fare in the chat and accept it if it looks right.",
}
ORDER = ["changeReason", "pnr", "passengerNames", "newTravelDate", "timeFlexibility",
         "contactEmail", "selectedFlight", "fareAcceptance"]

RULES = """You are a friendly airline agent on a phone-style voice call. You help the caller change one existing flight booking.
You speak through text to speech. Keep every reply to one or two short sentences. Never use lists, markdown, emoji or dashes.

What you collect
- By voice: the reason for the change (changeReason), the new travel date (newTravelDate) and the time of day (timeFlexibility: morning, afternoon, evening or any).
- In the chat box: the booking reference (pnr), the passenger names (passengerNames), an optional email (contactEmail), the new flight (selectedFlight) and the fare acceptance (fareAcceptance). Letters, digits and names are hard to hear, so these are typed.

How to work
- Right after you hear the reason, save it with record_answer and call send_chat_request for pnr. Tell the caller you sent a box to the chat for their booking reference.
- Say a box was sent only when send_chat_request answers "Sent to the chat." If it says the box is queued, do not mention it yet.
- When a turn needs several tools (for example saving an answer and sending a chat box), call them together in one step.
- Save every spoken answer at once with record_answer. For dates, look the day up in the calendar below and send YYYY-MM-DD. Never work out a weekday yourself. After saving a date, read back the exact words the tool returns.
- Save the reason only when the caller actually gives one, not a greeting. If they explain it better later, save it again.
- If a tool returns an error sentence, say it to the caller in your own short words and ask again.
- One step at a time. Ask no new spoken question while a chat box is open. Tell the caller once what to do in the chat (type it, pick one, or tap Skip on the optional email), then wait quietly until a note says it was submitted. If the caller gives a spoken answer anyway, save it, then remind them about the box.
- The email box is optional. Say they can type an email for the e-ticket or tap Skip.
- When a note says no chat box is open, go on with the next spoken question (reason, then date, then time of day).
- Once the booking reference, date and time of day are set, call send_chat_request for selectedFlight, then for fareAcceptance after a flight is picked. Tell the caller to pick a flight and check the fare in the chat.
- If the caller says a booking reference, name or email aloud, call note_spoken_value, then ask them to type it in the chat.
- If a tool says the call and the chat disagree, ask the caller which value is right and call resolve_conflict.
- If the caller wants a refund instead of a new flight, call switch_to_refund and tell them a person will process the refund.
- If the caller wants to stop, confirm once. Only after they confirm, call stop_request.
- Notes that start with "The user just submitted" come from the chat. Acknowledge them briefly and move on.
- When a tool result or note says the session is complete, say the summary it gives you, say goodbye and call end_call.
- Use check_status if you are unsure what is still missing.

Never
- Never say a flight number, time or fare that did not come from a tool result or the chat.
- Never read passenger names aloud and never ask for them by voice. You do not know them.
- Never promise a fee waiver or a refund of the change fee.
- Never ask for card numbers or payment details."""


def _fields(ctx: dict) -> dict:
    return (ctx.get("state") or {}).get("fields") or {}


def _next_missing(ctx: dict) -> str | None:
    fields = _fields(ctx)
    for name in ORDER:
        if (fields.get(name) or {}).get("status") != "valid":
            return name
    return None


def calendar(today_iso: str, days: int = 15) -> str:
    """The next two weeks with weekdays, so the LLM never does date arithmetic."""
    try:
        start = date.fromisoformat(today_iso)
    except (TypeError, ValueError):
        return ""
    return "; ".join(f"{d:%a %d %b} = {d.isoformat()}" for d in (start + timedelta(n) for n in range(days)))


def system_prompt(ctx: dict) -> str:
    lines = [RULES, "", f"Today is {ctx.get('weekday', '')} {ctx.get('today', '')} (India time).",
             f"Calendar: {calendar(ctx.get('today', ''))}."]
    b = ctx.get("bookingSummary")
    if b:
        lines.append(f"The booking is {b['from']} to {b['to']} on {b['date']} at {b['time']}, "
                     f"{b['pax']} passenger(s), {b['fareClass']} fare.")
    fields = _fields(ctx)
    if fields:
        status = ", ".join(f"{k}: {v.get('status')}" for k, v in fields.items())
        lines.append(f"Field status so far: {status}.")
    card = ctx.get("openCard")
    if card:
        lines.append(f"A chat box is open now: {card.get('label')}. The caller must finish it before anything else.")
    state = ctx.get("state") or {}
    if state.get("requestType") == "refund":
        lines.append("The caller asked for a refund instead. Only the reason, booking reference and names are needed.")
    return "\n".join(lines)


def resume_line(ctx: dict) -> str | None:
    """After a drop or restart: apologise and ask again for what we were on."""
    if not ctx.get("transcript"):
        return None
    focus = ctx.get("focus")
    if not focus or (_fields(ctx).get(focus) or {}).get("status") == "valid":
        focus = _next_missing(ctx)
    question = QUESTIONS.get(focus or "", "How can I help with the rest of your change?")
    return f"Sorry, we got cut off. {question}"


def event_note(kind: str, payload: dict) -> str | None:
    if kind == "fieldUpdate":
        field, status, summary = payload.get("field"), payload.get("status"), payload.get("summary", "")
        if status == "valid":
            head = f"The user just submitted {field} in chat. It is valid. {summary}".strip()
        else:
            head = f"The user just submitted {field} in chat. It is not valid: {summary}".strip()
        if "openCard" not in payload:
            return head
        card = payload.get("openCard")
        if not card:
            return f"{head} No chat box is open now. Continue with the next spoken question."
        skip = " or tap Skip" if card.get("optional") else ""
        return (f"{head} The chat now shows a box for: {card.get('label')}. In one short sentence, ask the caller "
                f"to fill it in{skip}. Ask nothing else until it is submitted.")
    if kind == "answer":
        return None  # the fieldUpdate that follows says the same, with the result
    if kind == "message":
        return f"The chat showed this message: {payload.get('text', '')}"
    if kind == "outcome":
        return (f"The session is complete with outcome {payload.get('outcome')}. "
                f"Tell the caller: {payload.get('summary', '')} Then say goodbye and call end_call.")
    return f"Chat event {kind}."

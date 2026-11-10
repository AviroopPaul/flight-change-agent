"""LLM tools. ToolLogic holds the behaviour (testable without LiveKit); FlightAgent exposes it as tools."""

import asyncio
import logging
import re
from typing import Literal

from livekit.agents import Agent, RunContext, function_tool, get_job_context

from backend_client import BackendClient
from prompts import clean_text, month_calendar

log = logging.getLogger("tools")
CallField = Literal["changeReason", "newTravelDate", "timeFlexibility"]
ChatField = Literal["pnr", "passengerNames", "contactEmail", "selectedFlight", "fareAcceptance"]
AnyField = Literal["changeReason", "newTravelDate", "timeFlexibility", "pnr", "passengerNames",
                   "contactEmail", "selectedFlight", "fareAcceptance"]


# Words that show the caller actually named a day. Without one, a "date" is the model's guess.
DATE_WORDS = re.compile(
    r"\d|\b(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|tonight|next|coming|week|weekend"
    r"|month|fortnight|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth"
    r"|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|thirtieth)\b",
    re.IGNORECASE,
)
NO_DATE_SAID = ("Not saved: the caller did not say a date. Do not guess one. Ask them for the new travel date "
                "again, or to pick it on the calendar in the chat.")


def speak(resp: dict) -> str:
    """Turn a backend reply into text the LLM can act on."""
    if not resp.get("ok"):
        return resp.get("error") or "Something went wrong. Please try again."
    result = resp.get("result")
    text = str(result) if result not in (None, "") else "Done."
    if resp.get("outcome"):
        text += (f" The session is complete ({resp['outcome']}). Say this to the caller: "
                 f"{resp.get('summary', '')} Then say goodbye and call end_call.")
    return text


class ToolLogic:
    def __init__(self, client: BackendClient) -> None:
        self.client = client

    async def record_answer(self, field: str, value: str, said: str = "") -> str:
        if field == "newTravelDate" and not DATE_WORDS.search(said or ""):
            return NO_DATE_SAID
        return speak(await self.client.submit_field(field, value))

    async def note_spoken_value(self, field: str, value: str) -> str:
        return speak(await self.client.submit_field(field, value))

    async def send_chat_request(self, field: str) -> str:
        return speak(await self.client.request_chat_input(field))

    async def resolve_conflict(self, field: str, choice: str) -> str:
        return speak(await self.client.resolve_conflict(field, choice))

    async def switch_to_refund(self) -> str:
        return speak(await self.client.refund_instead())

    async def stop_request(self) -> str:
        return speak(await self.client.opt_out())

    async def end_call_blocker(self, caller_is_leaving: bool) -> str | None:
        """Why the agent must not hang up yet, or None. A request still open in the chat keeps the call
        going, unless the caller says they must leave. If the backend is down, never trap the caller."""
        if caller_is_leaving:
            return None
        ctx = await self.client.context()
        if not ctx.get("ok") or (ctx.get("state") or {}).get("locked"):
            return None
        card = ctx.get("openCard")
        left = f" The chat box for {card['label']} is still open." if card else ""
        return ("Not hung up: the request is not finished." + left + " Do not say goodbye. Tell the caller "
                "what is left and wait. Only if they say they must go, tell them they can finish in the chat, "
                "then call end_call with caller_is_leaving true.")

    async def check_status(self) -> str:
        ctx = await self.client.context()
        if not ctx.get("ok"):
            return ctx.get("error", "I couldn't check right now.")
        state = ctx.get("state") or {}
        parts = ["Fields: " + ", ".join(f"{k}: {v.get('status')}" for k, v in (state.get("fields") or {}).items())]
        card = ctx.get("openCard")
        parts.append(f"open in chat: {card['field']}" if card else "nothing open in chat")
        b = ctx.get("bookingSummary")
        if b:
            parts.append(f"booking {b['from']} to {b['to']} on {b['date']} at {b['time']}, {b['pax']} passenger(s)")
        for c in state.get("openConflicts") or []:
            parts.append(f"conflict on {c['field']}: call says {c['callValue']}, chat says {c['chatValue']}")
        if state.get("locked"):
            parts.append(f"the session is complete ({state.get('outcome')}); say goodbye and call end_call")
        return ". ".join(parts) + "."


class FlightAgent(Agent):
    def __init__(self, client: BackendClient, instructions: str) -> None:
        super().__init__(instructions=instructions)
        self.logic = ToolLogic(client)

    async def llm_node(self, chat_ctx, tools, model_settings):
        """The default LLM node, with dashes removed from spoken text."""
        async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
            if isinstance(chunk, str):
                yield clean_text(chunk)
                continue
            delta = getattr(chunk, "delta", None)
            if delta is not None and getattr(delta, "content", None):
                delta.content = clean_text(delta.content)
            yield chunk

    @function_tool()
    async def record_answer(self, context: RunContext, field: CallField, value: str, said: str = "") -> str:
        """Save a spoken answer. newTravelDate must be YYYY-MM-DD. timeFlexibility is morning, afternoon, evening or any.
        said: the caller's exact words for this answer. Required for newTravelDate."""
        return await self.logic.record_answer(field, value, said)

    @function_tool()
    async def note_spoken_value(self, context: RunContext, field: ChatField, value: str) -> str:
        """Record a booking reference, name or email the caller said aloud. It is only a hint; ask them to type it."""
        return await self.logic.note_spoken_value(field, value)

    @function_tool()
    async def send_chat_request(self, context: RunContext, field: AnyField) -> str:
        """Show an input box in the caller's chat for a field. Only one box shows at a time; later ones queue."""
        return await self.logic.send_chat_request(field)

    @function_tool()
    async def resolve_conflict(self, context: RunContext, field: CallField,
                               choice: Literal["callValue", "chatValue"]) -> str:
        """After the caller confirms which value is right when the call and the chat disagree."""
        return await self.logic.resolve_conflict(field, choice)

    @function_tool()
    async def switch_to_refund(self, context: RunContext) -> str:
        """The caller wants a refund instead of a new flight."""
        return await self.logic.switch_to_refund()

    @function_tool()
    async def stop_request(self, context: RunContext) -> str:
        """Stop the whole request. Only after the caller has confirmed they want to stop."""
        return await self.logic.stop_request()

    @function_tool(name="month_calendar")
    async def month_calendar_tool(self, context: RunContext, month: str) -> str:
        """Every day of a month (YYYY-MM) with its weekday. Use it for a weekday named beyond the two weeks listed."""
        return month_calendar(month)

    @function_tool()
    async def check_status(self, context: RunContext) -> str:
        """What is filled in, what is missing, and what is open in the chat."""
        return await self.logic.check_status()

    @function_tool()
    async def end_call(self, context: RunContext, caller_is_leaving: bool = False) -> str:
        """Hang up after you have said goodbye. Set caller_is_leaving only when the caller says they must go
        before the request is finished."""
        blocker = await self.logic.end_call_blocker(caller_is_leaving)
        if blocker:
            return blocker
        await context.wait_for_playout()
        job = get_job_context()

        async def _hangup() -> None:
            await asyncio.sleep(0.5)
            await job.delete_room()

        asyncio.create_task(_hangup())
        return "Call ending."

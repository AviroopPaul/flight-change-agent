import httpx
import respx

from backend_client import BackendClient
from tools import ToolLogic
from turns import TurnTracker

BASE = "http://backend.test"
SID = "s_abc"


def client():
    return BackendClient(BASE, "tok-123", SID)


@respx.mock
async def test_record_answer_returns_backend_error_text():
    respx.post(f"{BASE}/internal/sessions/{SID}/fields").mock(return_value=httpx.Response(
        200, json={"ok": False, "error": "Please give the date as a day, month and year."}))
    out = await ToolLogic(client()).record_answer("newTravelDate", "Dec 13th")
    assert out == "Please give the date as a day, month and year."


@respx.mock
async def test_tools_send_bearer_token():
    route = respx.post(f"{BASE}/internal/sessions/{SID}/chat-input").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": "Sent to the chat."}))
    out = await ToolLogic(client()).send_chat_request("pnr")
    assert route.called and route.calls[0].request.headers["authorization"] == "Bearer tok-123"
    assert out == "Sent to the chat."


@respx.mock
async def test_outcome_reply_tells_agent_to_wrap_up():
    respx.post(f"{BASE}/internal/sessions/{SID}/opt-out").mock(return_value=httpx.Response(
        200, json={"ok": True, "result": "Stopped.", "outcome": "optedOut", "summary": "Okay, I've stopped."}))
    out = await ToolLogic(client()).stop_request()
    assert "Okay, I've stopped." in out and "end_call" in out


@respx.mock
async def test_backend_down_gives_speakable_error():
    respx.post(f"{BASE}/internal/sessions/{SID}/fields").mock(side_effect=httpx.ConnectError("down"))
    out = await ToolLogic(client()).record_answer("changeReason", "work")
    assert out.startswith("I couldn't save that")


@respx.mock
async def test_check_status_summarizes_without_names():
    respx.get(f"{BASE}/internal/sessions/{SID}/context").mock(return_value=httpx.Response(200, json={
        "ok": True, "focus": "pnr", "today": "2026-11-07", "transcript": [],
        "openCard": {"id": "r1", "field": "pnr", "kind": "text", "label": "Booking reference (PNR)"},
        "bookingSummary": {"route": "BLR-DEL", "from": "BLR", "to": "DEL", "date": "2026-11-12",
                           "time": "07:05", "pax": 1, "fareClass": "saver"},
        "state": {"requestType": "change", "locked": False, "outcome": None, "openConflicts": [],
                  "fields": {"pnr": {"status": "valid"}, "changeReason": {"status": "missing"}}}}))
    out = await ToolLogic(client()).check_status()
    assert "pnr: valid" in out and "changeReason: missing" in out and "BLR to DEL" in out
    assert "open in chat: pnr" in out


def test_turn_tracker_emits_when_complete():
    t = TurnTracker()
    assert t.add("sp1", eou_ms=300) is None
    assert t.add("sp1", llm_ttft_ms=400) is None
    assert t.add("sp1", tts_ttfb_ms=250) == {"eouMs": 300, "llmTtftMs": 400, "ttsTtfbMs": 250}
    assert t.add("sp1", tts_ttfb_ms=999) is None  # reported once


def test_tool_schemas_have_no_ambiguous_unions():
    """Groq rejects anyOf branches that share a primitive type (seen in a live call)."""
    import json as _json

    from livekit.agents.llm import utils

    from tools import FlightAgent

    agent = FlightAgent(client(), instructions="x")
    for tool in agent.tools:
        schema = _json.dumps(utils.build_legacy_openai_schema(tool))
        assert "anyOf" not in schema, schema


def test_no_round_trip_only_tools():
    """Each tool call is a full LLM round trip; focus and category are handled by the backend."""
    from tools import FlightAgent

    names = {t.info.name if hasattr(t, "info") else t.__name__ for t in FlightAgent(client(), instructions="x").tools}
    assert "set_focus" not in names and "set_reason_category" not in names
    assert {"record_answer", "send_chat_request", "end_call"} <= names

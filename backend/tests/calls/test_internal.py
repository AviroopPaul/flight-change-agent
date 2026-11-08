import asyncio
import json

from app.chat.service import handle_client
from tests.calls.conftest import AUTH


def url(sid, path):
    return f"/internal/sessions/{sid}{path}"


async def test_internal_requires_token(client, lk, sid):
    assert (await client.get(url(sid, "/context"))).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert (await client.post(url(sid, "/fields"), json={"field": "pnr", "value": "x"}, headers=bad)).status_code == 401


async def test_fields_messy_date_returns_speakable_error(client, lk, sid):
    r = await client.post(url(sid, "/fields"), json={"field": "newTravelDate", "value": "Dec 13th"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"ok": False, "error": "Please give the date as a day, month and year."}


async def test_fields_ok(client, lk, sid):
    r = await client.post(url(sid, "/fields"), json={"field": "timeFlexibility", "value": "Any time"}, headers=AUTH)
    assert r.json()["ok"] is True and r.json()["result"].startswith("any")


async def test_unknown_field_ok_false(client, lk, sid):
    for path, body in [("/fields", {"field": "shoe", "value": 1}), ("/chat-input", {"field": "shoe"}),
                       ("/focus", {"field": "shoe"})]:
        r = await client.post(url(sid, path), json=body, headers=AUTH)
        assert r.status_code == 200 and r.json() == {"ok": False, "error": "Unknown field."}


async def test_garbage_body_is_ok_false(client, lk, sid):
    r = await client.post(url(sid, "/fields"), content=b"not json", headers=AUTH)
    assert r.status_code == 200 and r.json()["ok"] is False


async def test_unknown_session_ok_false(client, lk):
    r = await client.post(url("s_nope", "/fields"), json={"field": "pnr", "value": "x"}, headers=AUTH)
    assert r.status_code == 200 and r.json() == {"ok": False, "error": "Unknown session."}


async def test_chat_answer_during_call_sends_room_event(client, lk, sid, app):
    await client.post(url(sid, "/call"), json={"active": True}, headers=AUTH)
    r = await client.post(url(sid, "/chat-input"), json={"field": "pnr"}, headers=AUTH)
    assert r.json() == {"ok": True, "result": "Sent to the chat."}
    ctx = (await client.get(url(sid, "/context"), headers=AUTH)).json()
    card = ctx["openCard"]
    assert card["field"] == "pnr"
    lk.sent.clear()
    await handle_client(app, sid, {"type": "inputResponse", "requestId": card["id"], "field": "pnr",
                                   "value": "ABC123"})
    await asyncio.sleep(0)  # room sends run as background tasks
    updates = [p for s, k, p in lk.sent if k == "fieldUpdate"]
    assert updates and updates[0]["field"] == "pnr" and updates[0]["status"] == "valid"
    assert "BLR to DEL" in updates[0]["summary"]


async def test_agent_tool_calls_are_not_echoed_to_call(client, lk, sid):
    await client.post(url(sid, "/call"), json={"active": True}, headers=AUTH)
    lk.sent.clear()
    await client.post(url(sid, "/fields"), json={"field": "changeReason", "value": "meeting moved"}, headers=AUTH)
    assert lk.sent == []


async def test_call_end_hands_over_to_chat(client, lk, sid, app):
    await client.post(url(sid, "/call"), json={"active": True}, headers=AUTH)
    ctx = (await client.get(url(sid, "/context"), headers=AUTH)).json()
    assert ctx["openCard"] is None
    r = await client.post(url(sid, "/call"), json={"active": False, "seconds": 75}, headers=AUTH)
    assert r.json()["ok"] is True
    ctx = (await client.get(url(sid, "/context"), headers=AUTH)).json()
    assert ctx["openCard"]["field"] == "pnr"
    assert ctx["state"]["calls"] == 1 and ctx["state"]["callSeconds"] == 75
    assert (await client.get(f"/sessions/{sid}")).json()["callActive"] is False


async def test_context_has_no_passenger_names(client, lk, sid, app):
    await client.post(url(sid, "/call"), json={"active": True}, headers=AUTH)
    await client.post(url(sid, "/fields"), json={"field": "passengerNames", "value": "Rahul Sharma"}, headers=AUTH)
    await client.post(url(sid, "/chat-input"), json={"field": "pnr"}, headers=AUTH)
    ctx = (await client.get(url(sid, "/context"), headers=AUTH)).json()
    await handle_client(app, sid, {"type": "inputResponse", "requestId": ctx["openCard"]["id"], "field": "pnr",
                                   "value": "ABC123"})
    await client.post(url(sid, "/chat-input"), json={"field": "passengerNames"}, headers=AUTH)
    ctx = (await client.get(url(sid, "/context"), headers=AUTH)).json()
    await handle_client(app, sid, {"type": "inputResponse", "requestId": ctx["openCard"]["id"],
                                   "field": "passengerNames", "value": "rahul sharma"})
    await client.post(url(sid, "/transcript"), json={"role": "user", "text": "hello there"}, headers=AUTH)
    ctx = (await client.get(url(sid, "/context"), headers=AUTH)).json()
    assert "RAHUL" not in json.dumps(ctx).upper()
    assert ctx["bookingSummary"]["route"] == "BLR-DEL" and ctx["bookingSummary"]["pax"] == 1
    assert ctx["state"]["fields"]["passengerNames"]["status"] == "valid"
    assert ctx["transcript"][-1] == {"role": "user", "text": "hello there"}
    assert len(ctx["today"]) == 10


async def test_focus_refund_optout_resolve(client, lk, sid):
    assert (await client.post(url(sid, "/focus"), json={"field": "pnr"}, headers=AUTH)).json()["ok"] is True
    ctx = (await client.get(url(sid, "/context"), headers=AUTH)).json()
    assert ctx["focus"] == "pnr"
    r = await client.post(url(sid, "/conflicts/newTravelDate/resolve"), json={"choice": "chatValue"}, headers=AUTH)
    assert r.json()["ok"] is False
    assert (await client.post(url(sid, "/reason-category"), json={"category": "medical"},
                              headers=AUTH)).json() == {"ok": True, "result": "medical"}
    assert (await client.post(url(sid, "/refund-instead"), headers=AUTH)).json()["ok"] is True
    r = (await client.post(url(sid, "/opt-out"), headers=AUTH)).json()
    assert r["ok"] is True and r["outcome"] == "optedOut" and r["summary"]


async def test_spoken_reason_gets_category(client, lk, sid, app):
    app.state.settings.groq_api_key = "k"
    import httpx
    import respx

    from app.sessions.classify import GROQ_URL

    with respx.mock(assert_all_called=False) as mock:
        mock.post(GROQ_URL).mock(return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "schedule"}}]}))
        mock.route(host="test").pass_through()
        r = await client.post(url(sid, "/fields"), json={"field": "changeReason", "value": "meeting moved"},
                              headers=AUTH)
    assert r.json()["ok"] is True
    ctx = (await client.get(url(sid, "/context"), headers=AUTH)).json()
    assert ctx["state"]["reasonCategory"] == "schedule"


async def test_context_says_if_a_call_was_still_active(client, lk, sid):
    ctx = (await client.get(url(sid, "/context"), headers=AUTH)).json()
    assert ctx["callActive"] is False
    await client.post(url(sid, "/call"), json={"active": True}, headers=AUTH)
    ctx = (await client.get(url(sid, "/context"), headers=AUTH)).json()
    assert ctx["callActive"] is True

"""HTTP access for testing: answer chat questions as the user, without a chat socket."""

import json


async def new_session(client):
    return (await client.post("/sessions")).json()["sessionId"]


async def answer(client, sid, value, request_id=None):
    body = {"value": value} if request_id is None else {"value": value, "requestId": request_id}
    return await client.post(f"/sessions/{sid}/answers", json=body)


async def test_first_answer_starts_the_chat_and_returns_the_next_card(client):
    sid = await new_session(client)
    r = await answer(client, sid, "abc 123")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["outcome"] is None and body["locked"] is False
    assert body["openCard"]["field"] == "passengerNames"
    view = (await client.get(f"/sessions/{sid}")).json()
    assert view["openCard"]["id"] == body["openCard"]["id"]


async def test_invalid_value_is_rejected_and_the_card_stays_open(client):
    sid = await new_session(client)
    r = await answer(client, sid, "CNX111")
    assert r.status_code == 422
    body = r.json()
    assert body["ok"] is False and "cancelled" in body["error"].lower()
    assert body["openCard"]["field"] == "pnr"


async def test_stale_request_id_gets_409(client):
    sid = await new_session(client)
    first = (await answer(client, sid, "ABC123")).json()
    r = await answer(client, sid, "RAHUL SHARMA", request_id="c_not_open")
    assert r.status_code == 409 and r.json()["error"] == "This question is no longer open."
    assert first["openCard"]["field"] == "passengerNames"


async def test_stop_then_confirm_opts_out_and_locks(client):
    sid = await new_session(client)
    r = await client.post(f"/sessions/{sid}/stop")
    assert r.status_code == 200 and r.json()["openCard"]["kind"] == "confirm"
    done = await answer(client, sid, True, request_id=r.json()["openCard"]["id"])
    assert done.status_code == 200 and done.json()["outcome"] == "optedOut" and done.json()["locked"] is True
    again = await answer(client, sid, "ABC123")
    assert again.status_code == 409


async def test_unknown_session_is_404(client):
    assert (await answer(client, "s_nope", "ABC123")).status_code == 404
    assert (await client.post("/sessions/s_nope/stop")).status_code == 404


async def test_whole_session_over_http_ends_completed_with_one_record(client, pool):
    from datetime import timedelta

    from app.core.clock import now_ist

    date = (now_ist() + timedelta(days=30)).date().isoformat()
    by_field = {"pnr": "ABC123", "passengerNames": "Mr. rahul sharma", "contactEmail": None,
                "changeReason": "Family wedding", "newTravelDate": date, "timeFlexibility": "afternoon",
                "fareAcceptance": True}
    sid = await new_session(client)
    body = (await answer(client, sid, "ABC123")).json()
    for _ in range(12):
        card = body["openCard"]
        if card is None:
            break
        value = card["options"][0]["value"] if card["field"] == "selectedFlight" else by_field[card["field"]]
        r = await answer(client, sid, value, request_id=card["id"])
        assert r.status_code == 200, r.text
        body = r.json()
    assert body["outcome"] == "completed" and body["locked"] is True
    async with pool.acquire() as c:
        rows = await c.fetch("select revision, outcome, payload from records where session_id=$1", sid)
    assert [(r["revision"], r["outcome"]) for r in rows] == [(1, "completed")]
    payload = rows[0]["payload"]
    payload = json.loads(payload) if isinstance(payload, str) else payload
    assert payload["fields"]["passengerNames"]["value"] == ["RAHUL SHARMA"]

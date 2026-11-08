from tests.calls.conftest import AUTH


async def _story(client, sid):
    u = f"/internal/sessions/{sid}"
    await client.post(f"{u}/call", json={"active": True}, headers=AUTH)
    await client.post(f"{u}/transcript", json={"role": "agent", "text": "What's the reason for the change?"}, headers=AUTH)
    await client.post(f"{u}/transcript", json={"role": "user", "text": "My meeting moved."}, headers=AUTH)
    await client.post(f"{u}/fields", json={"field": "changeReason", "value": "my meeting moved"}, headers=AUTH)
    await client.post(f"{u}/fields", json={"field": "newTravelDate", "value": "Dec 13th"}, headers=AUTH)
    await client.post(f"{u}/metrics", json={"eouMs": 300, "llmTtftMs": 400, "ttsTtfbMs": 250}, headers=AUTH)


async def test_timeline_merges_both_channels_tools_and_metrics(client, lk, sid):
    await _story(client, sid)
    r = await client.get(f"/sessions/{sid}/timeline")
    assert r.status_code == 200
    t = r.json()
    entries = t["entries"]
    assert [e["at"] for e in entries] == sorted(e["at"] for e in entries)
    lanes = {e["lane"] for e in entries}
    assert {"call", "agent", "system"} <= lanes
    assert any(e["lane"] == "call" and e["detail"] == "My meeting moved." for e in entries)
    tool = next(e for e in entries if e["lane"] == "agent" and e["data"]["args"].get("field") == "changeReason")
    assert tool["ok"] is True and tool["title"] == "record_answer"
    bad = next(e for e in entries if e["lane"] == "agent" and e["data"]["args"].get("field") == "newTravelDate")
    assert bad["ok"] is False and bad["detail"]  # the error the agent was given
    assert any(e["kind"] == "latency" and e["data"]["totalMs"] == 950 for e in entries)

    s = t["summary"]
    assert s["sessionId"] == sid and s["calls"] == 1
    assert s["fields"]["changeReason"]["status"] == "valid"
    assert s["latency"] == {"turns": 1, "p50Ms": 950.0, "p95Ms": 950.0, "maxMs": 950.0}
    assert s["toolErrors"] == 1 and s["toolCalls"] >= 2


async def test_timeline_unknown_session_404(client):
    r = await client.get("/sessions/s_nope/timeline")
    assert r.status_code == 404

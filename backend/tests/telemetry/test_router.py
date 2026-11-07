from tests.calls.conftest import AUTH


async def test_usage_and_metrics_feed_cost(client, lk, sid, pool):
    u = f"/internal/sessions/{sid}"
    for kind, q in [("stt_seconds", 240), ("tts_chars", 2000), ("llm_in_tokens", 20000), ("llm_out_tokens", 3000)]:
        r = await client.post(f"{u}/usage", json={"kind": kind, "quantity": q}, headers=AUTH)
        assert r.json() == {"ok": True}
    r = await client.post(f"{u}/metrics", json={"eouMs": 300, "llmTtftMs": 400, "ttsTtfbMs": 250}, headers=AUTH)
    assert r.json() == {"ok": True}
    async with pool.acquire() as c:
        assert await c.fetchval("select total_ms from turn_metrics where session_id=$1", sid) == 950
    rec = (await client.post(f"{u}/opt-out", headers=AUTH)).json()
    assert rec["ok"] is True
    async with pool.acquire() as c:
        payload = await c.fetchval("select payload from records where session_id=$1", sid)
    assert payload["costUsd"] == 0.1043


async def test_bad_usage_kind_ok_false(client, lk, sid):
    r = await client.post(f"/internal/sessions/{sid}/usage", json={"kind": "x", "quantity": "abc"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["ok"] is False

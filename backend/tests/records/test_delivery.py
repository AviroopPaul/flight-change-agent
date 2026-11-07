from app.core.db import create_pool
from app.records.service import deliver_pending
from app.sessions.service import apply, create_session
from tests.conftest import TEST_DATABASE_URL, TEST_TOKEN
from tests.helpers import NOW, completing

AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}


async def test_restart_between_write_and_delivery(pool, client):
    sid = await create_session(pool, "iphash", NOW)
    await apply(pool, sid, completing, now=NOW, user_activity=True)
    # simulated restart: a fresh pool, delivery runs twice (startup + sweep)
    fresh = await create_pool(TEST_DATABASE_URL)
    try:
        n1 = await deliver_pending(fresh, client, "http://test/stub/records", TEST_TOKEN)
        n2 = await deliver_pending(fresh, client, "http://test/stub/records", TEST_TOKEN)
        assert (n1, n2) == (1, 0)
        async with fresh.acquire() as c:
            assert await c.fetchval("select count(*) from stub_records") == 1
            assert await c.fetchval("select delivered_at is not null from records where session_id=$1", sid)
    finally:
        await fresh.close()
    r = await client.get(f"/stub/records?sessionId={sid}")
    [item] = r.json()["records"]
    assert item["idempotencyKey"] == f"{sid}:1" and item["record"]["outcome"] == "completed"


async def test_failed_delivery_counts_attempts(pool, client):
    sid = await create_session(pool, "iphash", NOW)
    await apply(pool, sid, completing, now=NOW, user_activity=True)
    assert await deliver_pending(pool, client, "http://test/nope", TEST_TOKEN) == 0
    async with pool.acquire() as c:
        assert await c.fetchval("select attempts from records where session_id=$1", sid) == 1


async def test_stub_dedupes_idempotency_key(client):
    body = {"sessionId": "s_x", "revision": 1, "outcome": "completed"}
    h = {**AUTH, "Idempotency-Key": "s_x:1"}
    r1 = await client.post("/stub/records", json=body, headers=h)
    r2 = await client.post("/stub/records", json=body, headers=h)
    assert r1.json() == {"ok": True, "duplicate": False}
    assert r2.json() == {"ok": True, "duplicate": True}
    listing = (await client.get("/stub/records")).json()["records"]
    assert len(listing) == 1 and "record" not in listing[0]


async def test_stub_requires_token(client):
    r = await client.post("/stub/records", json={}, headers={"Idempotency-Key": "k"})
    assert r.status_code == 401

from datetime import timedelta

import httpx
import pytest

from app.jobs.service import sweep
from app.sessions import engine
from app.sessions.models import Conflict, FieldState, Result
from app.sessions.service import apply, create_session, load, mark_chat_connected, touch_call
from tests.conftest import TEST_TOKEN
from tests.helpers import NOW


@pytest.fixture
async def http(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        app.state.http = c
        yield c


async def records(pool, sid):
    async with pool.acquire() as c:
        return [r["outcome"] for r in await c.fetch(
            "select outcome from records where session_id=$1 order by revision", sid)]


async def test_idle_incomplete_becomes_partial(app, pool, http):
    sid = await create_session(pool, "h", NOW)
    out = await sweep(app, NOW + timedelta(minutes=31))
    assert out["closed"] == 1 and out["delivered"] == 1
    assert await records(pool, sid) == ["partial"]
    assert (await load(pool, sid)).locked is False


async def test_recent_activity_not_partial(app, pool, http):
    sid = await create_session(pool, "h", NOW)
    out = await sweep(app, NOW + timedelta(minutes=10))
    assert out["closed"] == 0 and await records(pool, sid) == []


async def test_active_call_not_partial(app, pool, http):
    sid = await create_session(pool, "h", NOW)
    await apply(pool, sid, lambda s, ca: engine.call_started(s), now=NOW, user_activity=False,
                set_call_active=True)
    await touch_call(pool, sid, NOW + timedelta(minutes=30), user_activity=False)  # agent still sending metrics
    out = await sweep(app, NOW + timedelta(minutes=31))
    assert out["closed"] == 0 and await records(pool, sid) == []


async def test_sweep_idempotent(app, pool, http):
    sid = await create_session(pool, "h", NOW)
    later = NOW + timedelta(minutes=31)
    await sweep(app, later)
    second = await sweep(app, later + timedelta(minutes=5))
    assert second == {"closed": 0, "delivered": 0, "chatStarted": 0, "callsReset": 0}
    assert await records(pool, sid) == ["partial"]


async def test_idle_with_conflict_needs_review(app, pool, http):
    sid = await create_session(pool, "h", NOW)

    def conflicted(s, ca):
        s = s.model_copy(deep=True)
        s.fields["newTravelDate"] = FieldState(status="invalid", error="conflict")
        s.conflicts.append(Conflict(field="newTravelDate", call_value="2026-12-14", chat_value="2026-12-13"))
        return Result(s)

    await apply(pool, sid, conflicted, now=NOW, user_activity=True)
    await sweep(app, NOW + timedelta(minutes=31))
    assert await records(pool, sid) == ["needsReview"]
    assert (await load(pool, sid)).locked is True


async def test_stale_call_flag_reset(app, pool, http):
    sid = await create_session(pool, "h", NOW)
    await apply(pool, sid, lambda s, ca: engine.call_started(s), now=NOW, user_activity=False,
                set_call_active=True)
    out = await sweep(app, NOW + timedelta(minutes=16))
    assert out["callsReset"] == 1
    async with pool.acquire() as c:
        assert await c.fetchval("select call_active from sessions where id=$1", sid) is False


async def test_chat_waiting_gets_first_card(app, pool, http):
    sid = await create_session(pool, "h", NOW)
    await mark_chat_connected(pool, sid, NOW)
    out = await sweep(app, NOW + timedelta(seconds=30))
    assert out["chatStarted"] == 1
    assert (await load(pool, sid)).open_card.field == "pnr"


async def test_sweep_endpoint_requires_token(client, http):
    assert (await client.post("/internal/sweep")).status_code == 401
    r = await client.post("/internal/sweep", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert r.status_code == 200 and set(r.json()) == {"closed", "delivered", "chatStarted", "callsReset"}


async def test_startup_sweep_delivers_leftover_record(pool, settings):
    import asyncio

    from asgi_lifespan import LifespanManager

    from app.main import create_app
    from tests.helpers import completing

    sid = await create_session(pool, "h", NOW)
    await apply(pool, sid, completing, now=NOW, user_activity=True)  # written, never delivered ("crash")
    settings.sweep_on_startup = True
    restarted = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url="http://test") as c:
        restarted.state.http = c
        async with LifespanManager(restarted):
            for _ in range(50):
                async with pool.acquire() as conn:
                    if await conn.fetchval("select count(*) from stub_records") == 1:
                        break
                await asyncio.sleep(0.05)
    async with pool.acquire() as conn:
        assert await conn.fetchval("select count(*) from stub_records") == 1
        assert await conn.fetchval("select delivered_at is not null from records where session_id=$1", sid)

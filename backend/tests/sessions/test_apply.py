import asyncio
from datetime import timedelta

from app.sessions import engine
from app.sessions.service import apply, create_session, events_since, load
from tests.helpers import NOW, completing, set_pnr


async def count(pool, sql, *args):
    async with pool.acquire() as c:
        return await c.fetchval(sql, *args)


async def test_apply_persists_state_and_events(pool):
    sid = await create_session(pool, "iphash", NOW)
    out = await apply(pool, sid, lambda s, ca: engine.advance(s, NOW, ca), now=NOW, user_activity=False)
    assert out.state.open_card.field == "pnr"
    assert [e.kind for e in out.events] == ["inputRequest"] and out.events[0].id > 0
    state = await load(pool, sid)
    assert state.open_card.id == out.state.open_card.id
    evs = await events_since(pool, sid, 0)
    assert [(k) for _, k, _ in evs] == ["inputRequest"]
    assert await count(pool, "select version from sessions where id=$1", sid) == 1


async def test_completed_writes_one_record_and_locks(pool):
    sid = await create_session(pool, "iphash", NOW)
    out = await apply(pool, sid, completing, now=NOW, user_activity=True)
    assert out.record["outcome"] == "completed" and out.record["revision"] == 1
    assert out.state.locked and out.state.revision == 1
    assert [e.kind for e in out.events][-1] == "record"
    assert await count(pool, "select count(*) from records where session_id=$1", sid) == 1
    assert await count(pool, "select locked from sessions where id=$1", sid) is True


async def test_record_written_once_even_if_apply_repeats(pool):
    sid = await create_session(pool, "iphash", NOW)
    await apply(pool, sid, completing, now=NOW, user_activity=True)
    out2 = await apply(pool, sid, completing, now=NOW, user_activity=True)
    assert out2.record is None
    assert await count(pool, "select count(*) from records where session_id=$1", sid) == 1


async def test_partial_then_return_creates_revision_2(pool):
    sid = await create_session(pool, "iphash", NOW)
    later = NOW + timedelta(minutes=31)
    out = await apply(pool, sid, lambda s, ca: engine.identity(s), now=later, user_activity=False, idle=True)
    assert out.record["outcome"] == "partial" and out.record["revision"] == 1
    assert not out.state.locked
    again = await apply(pool, sid, lambda s, ca: engine.identity(s), now=later, user_activity=False, idle=True)
    assert again.record is None
    back = await apply(pool, sid, set_pnr, now=later, user_activity=True)
    assert back.record is None and back.state.last_outcome is None
    out3 = await apply(pool, sid, lambda s, ca: engine.identity(s), now=later + timedelta(minutes=31),
                       user_activity=False, idle=True)
    assert out3.record["revision"] == 2 and out3.record["outcome"] == "partial"
    assert await count(pool, "select count(*) from records where session_id=$1", sid) == 2


async def test_concurrent_answers_one_wins(pool):
    sid = await create_session(pool, "iphash", NOW)
    out = await apply(pool, sid, lambda s, ca: engine.advance(s, NOW, ca), now=NOW, user_activity=False)
    cid = out.state.open_card.id

    def answer(s, ca):
        return engine.answer_card(s, cid, "ABC123", NOW, ca)

    a, b = await asyncio.gather(
        apply(pool, sid, answer, now=NOW, user_activity=True),
        apply(pool, sid, answer, now=NOW, user_activity=True),
    )
    kinds = [e.kind for e in a.events + b.events]
    assert kinds.count("answer") == 1 and kinds.count("inputError") == 1
    evs = await events_since(pool, sid, 0)
    assert [k for _, k, _ in evs].count("answer") == 1

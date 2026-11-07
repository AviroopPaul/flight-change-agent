"""SQL for transcript, usage and turn metrics."""


async def usage_rows(conn, session_id: str) -> list[tuple[str, float]]:
    rows = await conn.fetch(
        "select kind, sum(quantity) as q from usage where session_id = $1 group by kind", session_id)
    return [(r["kind"], float(r["q"])) for r in rows]


async def add_turn(conn, session_id: str, role: str, text: str) -> None:
    await conn.execute("insert into transcript (session_id, role, text) values ($1, $2, $3)", session_id, role, text)


async def last_turns(conn, session_id: str, n: int) -> list[dict]:
    rows = await conn.fetch(
        "select role, text from (select id, role, text from transcript where session_id = $1"
        " order by id desc limit $2) t order by id", session_id, n)
    return [{"role": r["role"], "text": r["text"]} for r in rows]


async def add_usage(conn, session_id: str, kind: str, quantity: float) -> None:
    await conn.execute("insert into usage (session_id, kind, quantity) values ($1, $2, $3)",
                       session_id, kind, quantity)


async def add_metrics(conn, session_id: str, eou: float, ttft: float, ttfb: float) -> None:
    await conn.execute(
        "insert into turn_metrics (session_id, eou_ms, llm_ttft_ms, tts_ttfb_ms, total_ms)"
        " values ($1, $2, $3, $4, $5)", session_id, eou, ttft, ttfb, eou + ttft + ttfb)


async def last_signal(conn, session_id: str):
    return await conn.fetchval(
        "select max(at) from (select max(at) as at from transcript where session_id = $1"
        " union all select max(at) from turn_metrics where session_id = $1) t", session_id)

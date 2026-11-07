"""SQL for transcript, usage and turn metrics."""


async def usage_rows(conn, session_id: str) -> list[tuple[str, float]]:
    rows = await conn.fetch(
        "select kind, sum(quantity) as q from usage where session_id = $1 group by kind", session_id)
    return [(r["kind"], float(r["q"])) for r in rows]

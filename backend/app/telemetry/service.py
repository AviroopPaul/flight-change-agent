from app.telemetry import repository as repo
from app.telemetry.pricing import cost_usd


async def session_cost(conn, session_id: str) -> float:
    return cost_usd(await repo.usage_rows(conn, session_id))

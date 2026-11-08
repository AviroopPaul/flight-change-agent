"""One session, start to end: both channels, the agent's tool calls, latency, cost and records.
The builder is pure; load() reads the rows."""

import statistics
from datetime import datetime

import asyncpg

from app.records import repository as records_repo
from app.sessions import service as sessions
from app.sessions.models import SessionState
from app.telemetry import repository as repo
from app.telemetry.service import session_cost

CALL, CHAT, AGENT, SYSTEM, RECORD = "call", "chat", "agent", "system", "record"


def _entry(at: datetime, lane: str, kind: str, title: str, detail: str | None = None,
           ok: bool | None = None, data: dict | None = None) -> dict:
    return {"at": at.isoformat(), "lane": lane, "kind": kind, "title": title, "detail": detail, "ok": ok,
            "data": data}


def _event(at: datetime, kind: str, p: dict) -> dict | None:
    if kind == "message":
        return _entry(at, CHAT, kind, "Agent message" if p.get("role") == "agent" else "User message", p.get("text"))
    if kind == "inputRequest":
        return _entry(at, CHAT, kind, f"Card opened: {p.get('field')}", p.get("label"), data={"kind": p.get("kind")})
    if kind == "answer":
        value = p.get("value")
        return _entry(at, CHAT, kind, f"Answered: {p.get('field')}", "(skipped)" if value is None else str(value))
    if kind == "inputError":
        return _entry(at, CHAT, kind, "Answer rejected", p.get("message"), ok=False)
    if kind == "inputCancel":
        return _entry(at, CHAT, kind, "Card cancelled", p.get("reason"))
    if kind == "fieldUpdate":
        valid = p.get("status") == "valid"
        return _entry(at, SYSTEM, kind, f"{p.get('field')}: {p.get('status')}", p.get("summary"), ok=valid)
    if kind == "record":
        r = p.get("record") or {}
        return _entry(at, RECORD, kind, f"Record revision {r.get('revision')}: {r.get('outcome')}",
                      r.get("outcomeReason"), data={"record": r})
    return None


def _tool(row: dict) -> dict:
    args = row["args"] or {}
    if row["name"] == "call":
        title = "Call started" if args.get("active") else f"Call ended ({args.get('seconds') or 0} s)"
        return _entry(row["at"], CALL, "call", title, ok=row["ok"])
    return _entry(row["at"], AGENT, "tool", row["name"], row["result"], ok=row["ok"], data={"args": args})


def _percentile(values: list[float], q: int) -> float:
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    return round(statistics.quantiles(vals, n=100, method="inclusive")[q - 1], 1)


def build(state: SessionState, created_at: datetime, events: list[tuple], turns: list[tuple], tools: list[dict],
          metrics: list[dict], revisions: list[dict], cost_usd: float) -> dict:
    entries = [e for e in (_event(at, kind, p) for _, kind, p, at in events) if e]
    entries += [_entry(at, CALL, "speech", "Caller" if role == "user" else "Agent (spoken)", text)
                for _, role, text, at in turns]
    entries += [_tool(t) for t in tools]
    entries += [_entry(m["at"], CALL, "latency", f"Turn latency {m['total_ms'] / 1000:.2f} s",
                       f"end of speech {m['eou_ms']:.0f} ms · LLM first token {m['llm_ttft_ms']:.0f} ms · "
                       f"TTS first byte {m['tts_ttfb_ms']:.0f} ms",
                       data={"totalMs": m["total_ms"], "eouMs": m["eou_ms"], "llmTtftMs": m["llm_ttft_ms"],
                             "ttsTtfbMs": m["tts_ttfb_ms"]})
                for m in metrics]
    entries += [_entry(r["delivered_at"], RECORD, "delivered", f"Record revision {r['revision']} delivered",
                       f"after {r['attempts']} attempt(s)" if r["attempts"] else None, ok=True)
                for r in revisions if r["delivered_at"]]
    entries.sort(key=lambda e: e["at"])

    totals = [m["total_ms"] for m in metrics]
    agent_tools = [t for t in tools if t["name"] != "call"]
    summary = {
        "sessionId": state.session_id,
        "createdAt": created_at.isoformat(),
        "requestType": state.request_type,
        "reasonCategory": state.reason_category,
        "outcome": state.last_outcome,
        "locked": state.locked,
        "revision": state.revision,
        "openCard": state.open_card.field if state.open_card else None,
        "fields": {name: {"status": f.status, "source": f.source, "value": f.value}
                   for name, f in state.fields.items()},
        "conflicts": [c.model_dump(by_alias=True, mode="json") for c in state.conflicts],
        "calls": state.calls,
        "callSeconds": state.call_seconds,
        "chatMessages": state.chat_messages,
        "costUsd": round(cost_usd, 4),
        "latency": {"turns": len(totals), "p50Ms": _percentile(totals, 50), "p95Ms": _percentile(totals, 95),
                    "maxMs": max(totals)} if totals else {"turns": 0},
        "toolCalls": len(agent_tools),
        "toolErrors": sum(1 for t in agent_tools if not t["ok"]),
        "records": [{"revision": r["revision"], "outcome": r["outcome"], "createdAt": r["created_at"].isoformat(),
                     "deliveredAt": r["delivered_at"].isoformat() if r["delivered_at"] else None}
                    for r in revisions],
    }
    return {"summary": summary, "entries": entries}


async def load(pool: asyncpg.Pool, session_id: str) -> dict | None:
    row = await sessions.get_row(pool, session_id)
    if row is None:
        return None
    state = await sessions.load(pool, session_id)
    events = await sessions.events_since(pool, session_id, 0)
    async with pool.acquire() as conn:
        turns = await repo.all_turns(conn, session_id)
        tools = await repo.tool_calls(conn, session_id)
        metrics = await repo.turn_metrics(conn, session_id)
        revisions = await records_repo.revisions(conn, session_id)
        cost = await session_cost(conn, session_id)
    return build(state, row["created_at"], events, turns, tools, metrics, revisions, cost)

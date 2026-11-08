"""Voice latency and cost report from the backend database.

Voice latency per agent turn = end-of-utterance delay + LLM time to first token + TTS time to first byte.

Usage (from backend/):
    uv run python ../scripts/latency_report.py --database-url "$NEON_DATABASE_URL" [--since 2026-11-07]
"""

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path


def percentiles(values: list[float]) -> dict:
    vals = sorted(float(v) for v in values)
    if not vals:
        return {"n": 0, "p50": None, "p95": None}
    if len(vals) == 1:
        return {"n": 1, "p50": vals[0], "p95": vals[0]}
    q = statistics.quantiles(vals, n=100)
    return {"n": len(vals), "p50": round(q[49], 1), "p95": round(q[94], 1)}


async def report(database_url: str, since: str | None) -> None:
    import asyncpg

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app.telemetry.pricing import cost_breakdown

    conn = await asyncpg.connect(database_url, statement_cache_size=0)
    try:
        where, args = ("where at >= $1::text::date", [since]) if since else ("", [])
        rows = await conn.fetch(f"select eou_ms, llm_ttft_ms, tts_ttfb_ms, total_ms from turn_metrics {where}", *args)
        total = percentiles([r["total_ms"] for r in rows])
        print(f"turns: {total['n']}")
        print(f"voice latency ms: p50 {total['p50']}  p95 {total['p95']}")
        for col, label in [("eou_ms", "end of utterance"), ("llm_ttft_ms", "LLM first token"),
                           ("tts_ttfb_ms", "TTS first byte")]:
            print(f"  {label:18} p50 {percentiles([r[col] for r in rows])['p50']}")

        rwhere = "and r.created_at >= $1::text::date" if since else ""
        recs = await conn.fetch(f"select r.session_id, r.payload from records r where r.outcome = 'completed' {rwhere}", *args)
        payloads = [(r["session_id"], json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"])
                    for r in recs]
        # Only sessions with a call: a chat-only session costs almost nothing and would hide the call cost.
        called = [(sid, p) for sid, p in payloads if (p.get("engagement") or {}).get("calls")]
        costs = [float(p["costUsd"]) for _, p in called]
        print(f"completed sessions: {len(payloads)}, with a call: {len(costs)}")
        if costs:
            print(f"cost per completed session with a call (USD): mean {statistics.mean(costs):.4f}"
                  f"  p50 {statistics.median(costs):.4f}  max {max(costs):.4f}")
        usage = await conn.fetch(
            "select kind, sum(quantity) as q from usage where session_id = any($1::text[]) group by kind",
            [sid for sid, _ in called])
        if usage and costs:
            per = {k: round(v / len(costs), 5) for k, v in cost_breakdown([(r["kind"], r["q"]) for r in usage]).items()}
            print(f"mean cost per completed session by part (USD): {per}")
    finally:
        await conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--since")
    args = ap.parse_args()
    asyncio.run(report(args.database_url, args.since))


if __name__ == "__main__":
    main()

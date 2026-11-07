"""Vendor prices in USD. Pure. Check the vendor pages when deploying."""

PRICES = {
    "deepgram_stt_per_min": 0.0077,
    "deepgram_tts_per_1k_chars": 0.030,
    "groq_in_per_m": 0.15,
    "groq_out_per_m": 0.60,
    "livekit_per_min": 0.0,
}

_UNIT_COST = {
    "stt_seconds": PRICES["deepgram_stt_per_min"] / 60,
    "tts_chars": PRICES["deepgram_tts_per_1k_chars"] / 1000,
    "llm_in_tokens": PRICES["groq_in_per_m"] / 1_000_000,
    "llm_out_tokens": PRICES["groq_out_per_m"] / 1_000_000,
    "call_seconds": PRICES["livekit_per_min"] / 60,
}


def cost_usd(usage_rows: list[tuple[str, float]]) -> float:
    total = sum(_UNIT_COST.get(kind, 0.0) * float(qty) for kind, qty in usage_rows)
    return round(total, 4)


def cost_breakdown(usage_rows: list[tuple[str, float]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for kind, qty in usage_rows:
        out[kind] = out.get(kind, 0.0) + _UNIT_COST.get(kind, 0.0) * float(qty)
    return {k: round(v, 6) for k, v in out.items()}

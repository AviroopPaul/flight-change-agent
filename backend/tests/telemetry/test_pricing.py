from app.telemetry.pricing import PRICES, cost_usd


def test_cost_usd():
    rows = [("stt_seconds", 240), ("tts_chars", 2000), ("llm_in_tokens", 20000),
            ("llm_out_tokens", 3000), ("call_seconds", 240)]
    assert cost_usd(rows) == 0.0956


def test_prices_table():
    assert PRICES["livekit_per_min"] == 0.0
    assert cost_usd([]) == 0.0
    assert cost_usd([("unknown", 5)]) == 0.0

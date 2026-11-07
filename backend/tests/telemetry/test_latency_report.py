import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "latency_report.py"


def load():
    spec = importlib.util.spec_from_file_location("latency_report", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_percentiles():
    out = load().percentiles([800, 900, 1000, 1100, 3000])
    assert out["n"] == 5 and out["p50"] == 1000 and out["p95"] > 1100


def test_percentiles_small_inputs():
    m = load()
    assert m.percentiles([]) == {"n": 0, "p50": None, "p95": None}
    assert m.percentiles([700]) == {"n": 1, "p50": 700, "p95": 700}

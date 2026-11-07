"""One cheap Groq call that maps a typed change reason to a category."""

import logging

import httpx

from app.sessions.fields import REASON_CATEGORIES

log = logging.getLogger("classify")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"
PROMPT = (
    "Classify why an airline customer wants to change their flight. "
    "Reply with exactly one word from this list: schedule, personal, medical, missedFlight, other."
)
_BY_LOWER = {c.lower(): c for c in REASON_CATEGORIES}


async def classify_reason(text: str, api_key: str, http: httpx.AsyncClient) -> str:
    if not api_key:
        return "other"
    try:
        resp = await http.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": MODEL, "reasoning_effort": "low", "temperature": 0, "max_completion_tokens": 200,
                  "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": text[:500]}]},
            timeout=6,
        )
        resp.raise_for_status()
        word = resp.json()["choices"][0]["message"]["content"].strip().strip(".").lower()
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        log.warning("classify failed: %s", exc)
        return "other"
    return _BY_LOWER.get(word, "other")

"""Joins per-turn latency parts (end of utterance, LLM first token, TTS first byte) by speech id."""


class TurnTracker:
    KEYS = ("eou_ms", "llm_ttft_ms", "tts_ttfb_ms")

    def __init__(self) -> None:
        self._parts: dict[str, dict[str, float]] = {}
        self._done: set[str] = set()

    def add(self, speech_id: str | None, **part: float) -> dict | None:
        if not speech_id or speech_id in self._done:
            return None
        parts = self._parts.setdefault(speech_id, {})
        parts.update(part)
        if all(k in parts for k in self.KEYS):
            self._done.add(speech_id)
            self._parts.pop(speech_id, None)
            return {"eouMs": parts["eou_ms"], "llmTtftMs": parts["llm_ttft_ms"], "ttsTtfbMs": parts["tts_ttfb_ms"]}
        return None

"""Typed client for the backend's /internal/* API. The agent keeps no state of its own."""

import logging
from typing import Any

import httpx

log = logging.getLogger("backend")
DOWN = "I couldn't save that just now. Please say it again in a moment."


class BackendClient:
    def __init__(self, base_url: str, token: str, session_id: str, http: httpx.AsyncClient | None = None):
        self.session_id = session_id
        self._base = f"{base_url.rstrip('/')}/internal/sessions/{session_id}"
        self._http = http or httpx.AsyncClient(timeout=8, headers={"Authorization": f"Bearer {token}"})
        if http is not None:
            self._http.headers["Authorization"] = f"Bearer {token}"

    async def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        try:
            r = await self._http.request(method, self._base + path, json=body)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("backend %s %s failed: %s", method, path, exc)
            return {"ok": False, "error": DOWN}

    async def context(self) -> dict:
        return await self._call("GET", "/context")

    async def submit_field(self, field: str, value: Any) -> dict:
        return await self._call("POST", "/fields", {"field": field, "value": value})

    async def request_chat_input(self, field: str) -> dict:
        return await self._call("POST", "/chat-input", {"field": field})

    async def resolve_conflict(self, field: str, choice: str) -> dict:
        return await self._call("POST", f"/conflicts/{field}/resolve", {"choice": choice})

    async def refund_instead(self) -> dict:
        return await self._call("POST", "/refund-instead")

    async def opt_out(self) -> dict:
        return await self._call("POST", "/opt-out")

    async def set_focus(self, field: str) -> dict:
        return await self._call("POST", "/focus", {"field": field})

    async def set_reason_category(self, category: str) -> dict:
        return await self._call("POST", "/reason-category", {"category": category})

    async def call_status(self, active: bool, seconds: int = 0) -> dict:
        return await self._call("POST", "/call", {"active": active, "seconds": seconds})

    async def transcript(self, role: str, text: str) -> dict:
        return await self._call("POST", "/transcript", {"role": role, "text": text})

    async def usage(self, kind: str, quantity: float) -> dict:
        return await self._call("POST", "/usage", {"kind": kind, "quantity": quantity})

    async def metrics(self, eou_ms: float, llm_ttft_ms: float, tts_ttfb_ms: float) -> dict:
        return await self._call("POST", "/metrics", {"eouMs": eou_ms, "llmTtftMs": llm_ttft_ms,
                                                     "ttsTtfbMs": tts_ttfb_ms})

    async def aclose(self) -> None:
        await self._http.aclose()

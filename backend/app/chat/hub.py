"""In-process fan-out of session events to chat sockets. One instance (max-instances=1)."""

import asyncio
from collections import defaultdict


class Hub:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs[session_id].add(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        self._subs[session_id].discard(q)
        if not self._subs[session_id]:
            self._subs.pop(session_id, None)

    def publish(self, session_id: str, event_id: int, kind: str, payload: dict) -> None:
        for q in list(self._subs.get(session_id, ())):
            q.put_nowait((event_id, kind, payload))

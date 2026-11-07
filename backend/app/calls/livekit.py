"""LiveKit server API: tokens, room + agent dispatch, data messages into the room."""

import json
import logging
from datetime import timedelta

from livekit import api

from app.core.config import Settings

log = logging.getLogger("livekit")
AGENT_NAME = "flight-agent"
EVENT_TOPIC = "session-events"
TOKEN_TTL = timedelta(minutes=15)
ROOM_TIMEOUT_S = 120


def room_name(session_id: str) -> str:
    return f"call-{session_id}"


class LiveKitBridge:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _api(self) -> api.LiveKitAPI:
        s = self.settings
        url = s.livekit_url.replace("wss://", "https://").replace("ws://", "http://")
        return api.LiveKitAPI(url, s.livekit_api_key, s.livekit_api_secret)

    def mint_token(self, session_id: str, identity: str) -> str:
        """Join this session's room only: mic publish + subscribe, no data publish, 15 minutes."""
        s = self.settings
        grants = api.VideoGrants(room_join=True, room=room_name(session_id), can_publish=True,
                                 can_subscribe=True, can_publish_data=False,
                                 can_publish_sources=["microphone"])
        return (api.AccessToken(s.livekit_api_key, s.livekit_api_secret)
                .with_identity(identity).with_name("Caller").with_grants(grants)
                .with_ttl(TOKEN_TTL).to_jwt())

    async def ensure_dispatch(self, session_id: str) -> None:
        room = room_name(session_id)
        async with self._api() as lk:
            await lk.room.create_room(api.CreateRoomRequest(
                name=room, empty_timeout=ROOM_TIMEOUT_S, departure_timeout=ROOM_TIMEOUT_S))
            existing = await lk.agent_dispatch.list_dispatch(room_name=room)
            if any(d.agent_name == AGENT_NAME for d in existing):
                return
            await lk.agent_dispatch.create_dispatch(api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME, room=room, metadata=json.dumps({"sessionId": session_id})))

    async def send_event(self, session_id: str, kind: str, payload: dict) -> None:
        try:
            async with self._api() as lk:
                await lk.room.send_data(api.SendDataRequest(
                    room=room_name(session_id), data=json.dumps({"kind": kind, "payload": payload}).encode(),
                    kind=api.DataPacket.Kind.RELIABLE, topic=EVENT_TOPIC))
        except Exception as exc:  # noqa: BLE001 - never break a request over a room message
            log.warning("send_event failed for %s: %s", session_id, exc)

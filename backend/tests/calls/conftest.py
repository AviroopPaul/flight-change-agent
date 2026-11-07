import pytest

from app.calls.livekit import LiveKitBridge
from tests.conftest import TEST_TOKEN

AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}


class FakeLiveKit(LiveKitBridge):
    def __init__(self, settings):
        super().__init__(settings)
        self.sent: list[tuple[str, str, dict]] = []
        self.dispatched: list[str] = []

    async def ensure_dispatch(self, session_id: str) -> None:
        self.dispatched.append(session_id)

    async def send_event(self, session_id: str, kind: str, payload: dict) -> None:
        self.sent.append((session_id, kind, payload))


@pytest.fixture
def lk(app, settings):
    fake = FakeLiveKit(settings)
    app.state.livekit = fake
    return fake


@pytest.fixture
async def sid(client):
    return (await client.post("/sessions")).json()["sessionId"]

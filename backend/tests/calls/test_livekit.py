import jwt

from app.calls.livekit import AGENT_NAME, room_name
from tests.calls.conftest import AUTH


def test_names():
    assert room_name("s_abc") == "call-s_abc" and AGENT_NAME == "flight-agent"


async def test_call_token_scoped_to_room(client, lk, sid, settings):
    r = await client.post(f"/sessions/{sid}/call-token")
    body = r.json()
    assert r.status_code == 200 and body["room"] == f"call-{sid}" and body["url"] == settings.livekit_url
    claims = jwt.decode(body["token"], settings.livekit_api_secret, algorithms=["HS256"],
                        options={"verify_aud": False})
    assert claims["video"]["room"] == f"call-{sid}" and claims["video"]["roomJoin"] is True
    assert claims["video"].get("canPublishData") is False
    assert claims["exp"] - claims.get("iat", claims["nbf"]) == 900
    assert lk.dispatched == [sid]


async def test_call_token_locked_409(client, lk, sid):
    await client.post(f"/internal/sessions/{sid}/opt-out", headers=AUTH)
    assert (await client.post(f"/sessions/{sid}/call-token")).status_code == 409


async def test_call_token_unknown_404(client, lk):
    assert (await client.post("/sessions/s_nope/call-token")).status_code == 404

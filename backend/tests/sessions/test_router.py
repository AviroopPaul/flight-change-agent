import httpx
import respx

from app.sessions.classify import GROQ_URL, classify_reason


def groq_reply(text):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


@respx.mock
async def test_chat_reason_gets_category():
    async with httpx.AsyncClient() as http:
        respx.post(GROQ_URL).mock(return_value=groq_reply(" Medical\n"))
        assert await classify_reason("I have a surgery that day", "k", http) == "medical"
        respx.post(GROQ_URL).mock(return_value=groq_reply("missedflight"))
        assert await classify_reason("I missed it", "k", http) == "missedFlight"
        respx.post(GROQ_URL).mock(return_value=groq_reply("banana"))
        assert await classify_reason("hmm", "k", http) == "other"
        respx.post(GROQ_URL).mock(return_value=httpx.Response(500))
        assert await classify_reason("hmm", "k", http) == "other"
    assert await classify_reason("hmm", "", http) == "other"


async def test_create_session_and_rate_limit(client):
    h = {"X-Forwarded-For": "203.0.113.9, 10.0.0.1"}
    for _ in range(10):
        r = await client.post("/sessions", headers=h)
        assert r.status_code == 200 and r.json()["sessionId"].startswith("s_")
    r = await client.post("/sessions", headers=h)
    assert r.status_code == 429
    assert r.json() == {"error": "Too many sessions from this network. Try again later."}
    other = await client.post("/sessions", headers={"X-Forwarded-For": "198.51.100.1"})
    assert other.status_code == 200


async def test_daily_cap(client, app):
    app.state.settings.daily_session_cap = 1
    assert (await client.post("/sessions")).status_code == 200
    r = await client.post("/sessions", headers={"X-Forwarded-For": "198.51.100.7"})
    assert r.status_code == 503


async def test_get_session(client):
    sid = (await client.post("/sessions")).json()["sessionId"]
    r = await client.get(f"/sessions/{sid}")
    assert r.json() == {"sessionId": sid, "locked": False, "outcome": None, "callActive": False}
    assert (await client.get("/sessions/s_nope")).status_code == 404

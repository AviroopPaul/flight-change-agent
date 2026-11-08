import asyncio

import pytest
from starlette.testclient import TestClient

from app.main import create_app
from app.sessions.service import apply
from tests.conftest import reset_schema
from tests.helpers import completing

WELCOME = "Hi! I can help you change your flight. Tap the call button above to start, or answer the questions here."


@pytest.fixture
def tc(settings):
    asyncio.run(reset_schema())
    with TestClient(create_app(settings)) as c:
        yield c


def new_session(tc):
    return tc.post("/sessions").json()["sessionId"]


def until(ws, pred, limit=20):
    seen = []
    for _ in range(limit):
        m = ws.receive_json()
        seen.append(m)
        if pred(m):
            return m, seen
    raise AssertionError(f"not found in {seen}")


def card_for(field):
    return lambda m: m["type"] == "inputRequest" and m["field"] == field


def test_ws_input_flow_pnr_ok_then_names_card(tc):
    sid = new_session(tc)
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        first = ws.receive_json()
        assert first["type"] == "message" and first["text"] == WELCOME and first["eventId"] > 0
        card, _ = until(ws, card_for("pnr"))
        ws.send_json({"type": "inputResponse", "requestId": card["id"], "field": "pnr", "value": "abc123"})
        names, seen = until(ws, card_for("passengerNames"))
        assert names["label"] == "Passenger 1 of 1: full name as on ID"
        assert not any(m["type"] == "message" and m.get("role") == "user" for m in seen)  # no live echo


def test_ws_stale_answer_gets_error(tc):
    sid = new_session(tc)
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        card, _ = until(ws, card_for("pnr"))
        ws.send_json({"type": "inputResponse", "requestId": card["id"], "field": "pnr", "value": "ABC123"})
        until(ws, card_for("passengerNames"))
        ws.send_json({"type": "inputResponse", "requestId": card["id"], "field": "pnr", "value": "ABC123"})
        err, _ = until(ws, lambda m: m["type"] == "inputError")
        assert err == {"type": "inputError", "requestId": card["id"], "message": "This question is no longer open."}


def test_ws_bad_value_gets_error_copy(tc):
    sid = new_session(tc)
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        card, _ = until(ws, card_for("pnr"))
        ws.send_json({"type": "inputResponse", "requestId": card["id"], "field": "pnr", "value": "CNX111"})
        err, _ = until(ws, lambda m: m["type"] == "inputError")
        assert err["message"] == "That booking is cancelled, so it can't be changed."


def test_ws_replays_history_after_reconnect(tc):
    sid = new_session(tc)
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        welcome = ws.receive_json()
        card, _ = until(ws, card_for("pnr"))
        ws.send_json({"type": "inputResponse", "requestId": card["id"], "field": "pnr", "value": "ABC123"})
        until(ws, card_for("passengerNames"))
    with tc.websocket_connect(f"/chat?sessionId={sid}&after={welcome['eventId']}") as ws:
        names, seen = until(ws, card_for("passengerNames"))
        texts = [m.get("text") for m in seen]
        assert WELCOME not in texts
        assert "Booking reference (PNR)" in texts  # the answered card replays as its question
        assert any(m.get("role") == "user" and m["text"] == "ABC123" for m in seen)
        assert not any(m["type"] == "inputRequest" and m["field"] == "pnr" for m in seen)
        assert all(m["eventId"] > welcome["eventId"] for m in seen)


def test_ws_full_replay_has_no_duplicate_welcome(tc):
    sid = new_session(tc)
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        until(ws, card_for("pnr"))
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        _, seen = until(ws, card_for("pnr"))
        assert [m.get("text") for m in seen].count(WELCOME) == 1


def test_ws_optout_confirm_produces_record(tc):
    sid = new_session(tc)
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        pnr, _ = until(ws, card_for("pnr"))
        ws.send_json({"type": "optOut"})
        confirm, seen = until(ws, card_for("__optOut"))
        assert confirm["kind"] == "confirm" and confirm["label"] == "Stop this request? Nothing will be changed."
        assert any(m["type"] == "inputCancel" and m["requestId"] == pnr["id"] for m in seen)
        ws.send_json({"type": "inputResponse", "requestId": confirm["id"], "field": "__optOut", "value": True})
        rec, _ = until(ws, lambda m: m["type"] == "record")
        assert rec["record"]["outcome"] == "optedOut"
    assert tc.get(f"/sessions/{sid}").json()["locked"] is True


def test_locked_session_rejects_answers(tc):
    sid = new_session(tc)
    pool = tc.app.state.pool
    tc.portal.call(lambda: apply(pool, sid, completing, now=__import__("tests.helpers").helpers.NOW,
                                 user_activity=True))
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        rec, _ = until(ws, lambda m: m["type"] == "record")
        assert rec["record"]["outcome"] == "completed"
        ws.send_json({"type": "inputResponse", "requestId": "r1", "field": "pnr", "value": "ABC123"})
        err, _ = until(ws, lambda m: m["type"] == "inputError")
        assert err["message"] == "This request is already submitted."


def test_ws_unknown_session_closes(tc):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect), tc.websocket_connect("/chat?sessionId=s_missing") as ws:
        ws.receive_json()


def test_ws_full_replay_includes_spoken_turns_in_order(tc):
    from tests.calls.conftest import AUTH
    sid = new_session(tc)
    turn = f"/internal/sessions/{sid}/transcript"
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        until(ws, card_for("pnr"))
    tc.post(turn, json={"role": "agent", "text": "What's the reason for the change?"}, headers=AUTH)
    tc.post(turn, json={"role": "user", "text": "I have to call in sick."}, headers=AUTH)
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        _, seen = until(ws, lambda m: m.get("text") == "I have to call in sick.")
    spoken = [m for m in seen if m.get("spoken")]
    assert [(m["role"], m["text"]) for m in spoken] == [
        ("agent", "What's the reason for the change?"), ("user", "I have to call in sick.")]
    assert all(m["type"] == "message" and "eventId" not in m for m in spoken)  # resume ids stay event ids
    order = [m.get("text") or m["type"] for m in seen]
    assert order.index(WELCOME) < order.index("inputRequest") < order.index("What's the reason for the change?")


def test_ws_resume_does_not_repeat_spoken_turns(tc):
    from tests.calls.conftest import AUTH
    sid = new_session(tc)
    with tc.websocket_connect(f"/chat?sessionId={sid}") as ws:
        welcome = ws.receive_json()
        tc.post(f"/internal/sessions/{sid}/transcript", json={"role": "user", "text": "hello"}, headers=AUTH)
        until(ws, card_for("pnr"))
    with tc.websocket_connect(f"/chat?sessionId={sid}&after={welcome['eventId']}") as ws:
        _, seen = until(ws, card_for("pnr"))
    assert not any(m.get("spoken") for m in seen)  # the call already showed them live

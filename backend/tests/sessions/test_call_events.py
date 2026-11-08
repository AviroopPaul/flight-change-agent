from app.sessions.effects import call_events
from app.sessions.models import Event, InputCard, new_state


def test_field_update_to_call_names_the_next_open_card():
    s = new_state("s1")
    s.open_card = InputCard(id="r4", field="contactEmail", kind="email", label="Email for your new e-ticket (optional)",
                            required=False)
    events = [Event("answer", {"field": "passengerNames"}), Event("fieldUpdate", {"field": "passengerNames", "status": "valid"}),
              Event("inputRequest", {"id": "r4"})]
    out = call_events(events, s)
    assert [k for k, _ in out] == ["answer", "fieldUpdate"]
    assert out[1][1]["openCard"] == {"field": "contactEmail", "label": "Email for your new e-ticket (optional)",
                                     "optional": True}


def test_field_update_to_call_says_when_no_card_is_open():
    out = call_events([Event("fieldUpdate", {"field": "contactEmail", "status": "valid"})], new_state("s1"))
    assert out[0][1]["openCard"] is None

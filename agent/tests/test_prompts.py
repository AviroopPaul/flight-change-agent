from prompts import GREETING, event_note, resume_line, system_prompt

CTX = {
    "ok": True, "today": "2026-11-07", "weekday": "Saturday", "focus": None, "transcript": [],
    "openCard": None, "bookingSummary": None,
    "state": {"requestType": "change", "locked": False, "outcome": None, "openConflicts": [],
              "fields": {f: {"status": "missing"} for f in [
                  "changeReason", "newTravelDate", "timeFlexibility", "pnr", "passengerNames",
                  "selectedFlight", "fareAcceptance", "contactEmail"]}},
}


def test_resume_line_when_transcript_exists():
    ctx = dict(CTX, transcript=[{"role": "agent", "text": "Hi"}], focus="pnr")
    line = resume_line(ctx)
    assert line.startswith("Sorry, we got cut off.") and "booking reference" in line


def test_resume_line_uses_next_missing_without_focus():
    ctx = dict(CTX, transcript=[{"role": "agent", "text": "Hi"}])
    assert "reason" in resume_line(ctx)


def test_no_resume_line_on_fresh_session():
    assert resume_line(CTX) is None


def test_system_prompt_has_rules_and_today():
    p = system_prompt(CTX)
    assert "2026-11-07" in p and "Saturday" in p
    assert "never" in p.lower() and "fare" in p.lower()
    assert "passenger names" in p.lower()
    assert "—" not in p and "—" not in GREETING


def test_event_note_for_valid_pnr():
    note = event_note("fieldUpdate", {"field": "pnr", "status": "valid",
                                      "summary": "Route BLR to DEL on 12 Nov at 07:05, 1 passenger."})
    assert note == ("The user just submitted pnr in chat. It is valid. "
                    "Route BLR to DEL on 12 Nov at 07:05, 1 passenger.")


def test_event_note_for_invalid_and_outcome():
    bad = event_note("fieldUpdate", {"field": "pnr", "status": "invalid", "summary": "That booking is cancelled."})
    assert "not valid" in bad and "cancelled" in bad
    out = event_note("outcome", {"outcome": "completed", "summary": "You're all set."})
    assert "You're all set." in out


def test_clean_text_removes_dashes():
    from prompts import clean_text

    assert clean_text("morning—afternoon") == "morning, afternoon"
    assert clean_text("a — b – c") == "a, b, c"
    assert clean_text("plain") == "plain"

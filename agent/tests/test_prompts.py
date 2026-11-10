from prompts import GREETING, event_note, resume_line, system_prompt

CTX = {
    "ok": True, "today": "2026-11-07", "weekday": "Saturday", "focus": None, "transcript": [],
    "openCard": None, "bookingSummary": None,
    "state": {"requestType": "change", "locked": False, "outcome": None, "openConflicts": [],
              "fields": {f: {"status": "missing"} for f in [
                  "changeReason", "newTravelDate", "timeFlexibility", "pnr", "passengerNames",
                  "selectedFlight", "fareAcceptance", "contactEmail"]}},
}


def test_resume_line_after_a_crash_mid_call():
    # The last call never ended cleanly (callActive still true): the caller was cut off.
    ctx = dict(CTX, transcript=[{"role": "agent", "text": "Hi"}], focus="pnr", callActive=True)
    line = resume_line(ctx)
    assert line.startswith("Sorry, we got cut off.") and "booking reference" in line


def test_resume_line_on_call_me_back():
    # The last call ended normally and the caller called back: welcome them, continue at the current step.
    ctx = dict(CTX, transcript=[{"role": "agent", "text": "Hi"}], focus="pnr", callActive=False)
    line = resume_line(ctx)
    assert line.startswith("Welcome back.") and "booking reference" in line and "cut off" not in line


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


def test_answer_events_add_no_note():
    """fieldUpdate already carries the answer; a second note only costs tokens."""
    assert event_note("answer", {"field": "pnr"}) is None


def test_system_prompt_has_two_week_calendar():
    p = system_prompt(CTX)
    assert "Fri 13 Nov = 2026-11-13" in p
    assert "Sat 21 Nov = 2026-11-21" in p


def test_event_note_names_the_open_card_and_says_wait():
    note = event_note("fieldUpdate", {"field": "passengerNames", "status": "valid", "summary": "All match.",
                                      "openCard": {"field": "contactEmail", "label": "Email for your new e-ticket (optional)",
                                                   "optional": True}})
    assert "Email for your new e-ticket" in note
    assert "Skip" in note and "Ask nothing else" in note


def test_event_note_without_open_card_says_continue():
    note = event_note("fieldUpdate", {"field": "contactEmail", "status": "valid", "summary": "Email saved.",
                                      "openCard": None})
    assert "No chat box is open" in note


def test_system_prompt_mentions_box_open_at_start():
    ctx = dict(CTX, openCard={"field": "pnr", "label": "Booking reference (PNR)", "required": True})
    assert "A chat box is open now: Booking reference (PNR)" in system_prompt(ctx)


def test_rules_say_one_step_at_a_time():
    p = system_prompt(CTX)
    assert "Ask no new spoken question while a chat box is open" in p


def test_event_note_for_the_date_calendar_allows_voice_or_pick():
    note = event_note("fieldUpdate", {"field": "contactEmail", "status": "valid", "summary": "Skipped.",
                                      "openCard": {"field": "newTravelDate", "label": "New travel date", "optional": False}})
    assert "calendar" in note and "say" in note and "Ask nothing else" not in note


def test_prompt_sets_no_booking_horizon():
    p = system_prompt(CTX)
    assert "month_calendar" in p and "not a limit" in p


def test_month_calendar_lists_every_day_with_weekday():
    from prompts import month_calendar
    out = month_calendar("2027-02")
    assert out.startswith("February 2027:") and "Mon 1 Feb = 2027-02-01" in out and "Sun 28 Feb = 2027-02-28" in out
    assert "2027-02-29" not in out


def test_month_calendar_rejects_bad_input():
    from prompts import month_calendar
    assert month_calendar("next month") == "Give the month as YYYY-MM, for example 2026-12."


def test_prompt_says_how_to_change_filled_answers():
    p = system_prompt(CTX)
    assert "the email or the booking reference, call send_chat_request for that field" in p and "tap No on the fare card" in p

from datetime import date, datetime

import pytest

from app.catalog.repository import load_bookings
from app.core.clock import IST
from app.core.result import Err, Ok
from app.sessions.fields import (
    CHAT_ORDER,
    REQUIRED_CHANGE,
    match_passenger,
    normalize_date,
    normalize_email,
    normalize_flex,
    normalize_name,
    normalize_pnr,
    normalize_reason,
)

NOW = datetime(2026, 11, 7, 10, 0, tzinfo=IST)
BOOKINGS = load_bookings(NOW)


def test_field_lists():
    assert CHAT_ORDER == ["pnr", "passengerNames", "contactEmail", "selectedFlight", "fareAcceptance"]
    assert "contactEmail" not in REQUIRED_CHANGE and len(REQUIRED_CHANGE) == 7


def test_pnr_normalizes_case_and_spaces():
    assert normalize_pnr(" abc 123 ", BOOKINGS, NOW) == Ok("ABC123")


@pytest.mark.parametrize(
    "raw,msg",
    [
        ("AB12", "A booking reference has 6 letters or digits, like ABC123."),
        ("ZZZ999", "I can't find a booking with that reference. Please check it."),
        ("CNX111", "That booking is cancelled, so it can't be changed."),
        ("OLD222", "That flight has already left or leaves in under 3 hours, so it can't be changed here."),
        ("SON333", "That flight has already left or leaves in under 3 hours, so it can't be changed here."),
    ],
)
def test_pnr_errors(raw, msg):
    assert normalize_pnr(raw, BOOKINGS, NOW) == Err(msg)


def test_normalize_name():
    assert normalize_name("  Dr.  meera   nair ") == "MEERA NAIR"
    assert normalize_name("MISS o'neil") == "ONEIL"


def test_name_match_ignores_titles_case_punct():
    assert match_passenger("mr. rahul  sharma", BOOKINGS["ABC123"], []) == Ok("RAHUL SHARMA")


def test_name_mismatch_hides_real_names():
    r = match_passenger("rahul sharma", BOOKINGS["PQR456"], [])
    assert isinstance(r, Err)
    assert r.message == "That name doesn't match a passenger on this booking. Please type it exactly as on the ID."
    for name in BOOKINGS["PQR456"].passengers:
        assert name.lower() not in r.message.lower()


def test_name_duplicate_rejected():
    r = match_passenger("Ananya Iyer", BOOKINGS["PQR456"], ["ANANYA IYER"])
    assert r == Err("You've already given that passenger.")


@pytest.mark.parametrize(
    "raw,dep,msg",
    [
        ("2026-11-06", None, "That date has passed. Please pick a future date."),
        ("2027-10-04", None, "We can only book up to 330 days ahead."),
        ("2026-11-12", "ABC123", "That's the same day as your current flight. Please pick a different date."),
        ("13/12", None, "Please give the date as a day, month and year."),
        ("Dec 13th", None, "Please give the date as a day, month and year."),
        ("2026-02-30", None, "Please give the date as a day, month and year."),
    ],
)
def test_date_rules(raw, dep, msg):
    current = BOOKINGS[dep].departure if dep else None
    assert normalize_date(raw, NOW, current) == Err(msg)


def test_date_ok():
    assert normalize_date("2026-12-13", NOW, BOOKINGS["ABC123"].departure) == Ok(date(2026, 12, 13))
    assert normalize_date("2027-10-03", NOW, None) == Ok(date(2027, 10, 3))


def test_flex_aliases():
    assert normalize_flex("Any time") == Ok("any")
    assert normalize_flex(" Morning ") == Ok("morning")
    assert normalize_flex("night") == Err("Please choose morning, afternoon, evening or any time.")


def test_email():
    assert normalize_email("A@B.co") == Ok("a@b.co")
    assert normalize_email("a@b") == Err("That email address doesn't look right.")


def test_reason():
    assert normalize_reason("  work meeting moved ") == Ok("work meeting moved")
    assert isinstance(normalize_reason("x"), Err)
    assert isinstance(normalize_reason("a" * 501), Err)


@pytest.mark.parametrize("raw", ["Hey.", "hi", "Okay", "yeah", "Hello!"])
def test_reason_rejects_fillers(raw):
    assert isinstance(normalize_reason(raw), Err)

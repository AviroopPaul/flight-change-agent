"""Field definitions, validators and normalizers. Pure: no I/O, no clock."""

import re
from datetime import date, datetime, timedelta
from typing import Literal

from app.catalog.models import Booking
from app.catalog.service import WINDOWS
from app.core.result import Err, Ok

FieldName = Literal[
    "changeReason", "newTravelDate", "timeFlexibility", "pnr",
    "passengerNames", "selectedFlight", "fareAcceptance", "contactEmail",
]
ALL_FIELDS: list[str] = [
    "changeReason", "newTravelDate", "timeFlexibility", "pnr",
    "passengerNames", "selectedFlight", "fareAcceptance", "contactEmail",
]
CALL_NATIVE = {"changeReason", "newTravelDate", "timeFlexibility"}
CHAT_NATIVE = {"pnr", "passengerNames", "contactEmail", "selectedFlight", "fareAcceptance"}
REQUIRED_CHANGE = [
    "changeReason", "newTravelDate", "timeFlexibility", "pnr",
    "passengerNames", "selectedFlight", "fareAcceptance",
]
REQUIRED_REFUND = ["pnr", "passengerNames", "changeReason"]
OPTIONAL = ["contactEmail"]
CHAT_ORDER = ["pnr", "passengerNames", "contactEmail", "selectedFlight", "fareAcceptance"]
REASON_CATEGORIES = ["schedule", "personal", "medical", "missedFlight", "other"]
MIN_HOURS_BEFORE = 3

E_PNR_FORMAT = "A booking reference has 6 letters or digits, like ABC123."
E_PNR_NOT_FOUND = "I can't find a booking with that reference. Please check it."
E_PNR_CANCELLED = "That booking is cancelled, so it can't be changed."
E_PNR_TOO_LATE = "That flight has already left or leaves in under 3 hours, so it can't be changed here."
E_NAME = "That name doesn't match a passenger on this booking. Please type it exactly as on the ID."
E_NAME_DUP = "You've already given that passenger."
E_DATE_FORMAT = "Please give the date as a day, month and year."
E_DATE_PAST = "That date has passed. Please pick a future date."
E_DATE_SAME = "That's the same day as your current flight. Please pick a different date."
E_FLEX = "Please choose morning, afternoon, evening or any time."
E_EMAIL = "That email address doesn't look right."
E_REASON = "Please tell me in a few words why you want to change the flight."

_TITLES = re.compile(r"^(MR|MRS|MS|MISS|DR|MASTER)\s+")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]+$")
FLEX_ALIASES = {"any time": "any", "anytime": "any", "flexible": "any"}


def normalize_pnr(raw, bookings: dict[str, Booking], now: datetime) -> Ok | Err:
    pnr = re.sub(r"\s+", "", str(raw or "")).upper()
    if not re.fullmatch(r"[A-Z0-9]{6}", pnr):
        return Err(E_PNR_FORMAT)
    booking = bookings.get(pnr)
    if booking is None:
        return Err(E_PNR_NOT_FOUND)
    if booking.status == "cancelled":
        return Err(E_PNR_CANCELLED)
    if booking.departure <= now + timedelta(hours=MIN_HOURS_BEFORE):
        return Err(E_PNR_TOO_LATE)
    return Ok(pnr)


def normalize_name(raw) -> str:
    text = re.sub(r"[^A-Z\s]", "", str(raw or "").upper())
    text = re.sub(r"\s+", " ", text).strip()
    return _TITLES.sub("", text).strip()


def match_passenger(raw, booking: Booking, already: list[str]) -> Ok | Err:
    name = normalize_name(raw)
    if name in already:
        return Err(E_NAME_DUP)
    if name and name in booking.passengers:
        return Ok(name)
    return Err(E_NAME)


def normalize_date(raw, now: datetime, current_departure: datetime | None) -> Ok | Err:
    text = str(raw or "").strip()
    if not _ISO_DATE.match(text):
        return Err(E_DATE_FORMAT)
    try:
        day = date.fromisoformat(text)
    except ValueError:
        return Err(E_DATE_FORMAT)
    today = now.date()
    if day < today:
        return Err(E_DATE_PAST)
    if current_departure is not None and day == current_departure.date():
        return Err(E_DATE_SAME)
    return Ok(day)


def normalize_flex(raw) -> Ok | Err:
    text = re.sub(r"\s+", " ", str(raw or "").strip().lower())
    text = FLEX_ALIASES.get(text, text)
    return Ok(text) if text in WINDOWS else Err(E_FLEX)


FILLERS = {"hey", "hi", "hello", "ok", "okay", "yes", "yeah", "yep", "no", "hmm", "um", "uh", "sure", "fine"}


def normalize_reason(raw) -> Ok | Err:
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    if re.sub(r"[^a-z ]", "", text.lower()).strip() in FILLERS:
        return Err(E_REASON)  # a greeting is not a reason (a live call saved "Hey.")
    return Ok(text) if 3 <= len(text) <= 500 else Err(E_REASON)


def normalize_email(raw) -> Ok | Err:
    text = str(raw or "").strip().lower()
    return Ok(text) if _EMAIL.match(text) else Err(E_EMAIL)

import json
from datetime import datetime, time, timedelta
from functools import cache
from pathlib import Path

from app.catalog.models import Booking

DATA = Path(__file__).resolve().parent / "data" / "bookings.json"


@cache
def _raw() -> tuple[dict, ...]:
    return tuple(json.loads(DATA.read_text()))


def _departure(offset: dict, now: datetime) -> datetime:
    if "hours" in offset:
        return now + timedelta(hours=offset["hours"])
    day = now.date() + timedelta(days=offset["days"])
    hh, mm = (int(x) for x in offset["time"].split(":"))
    return datetime.combine(day, time(hh, mm), tzinfo=now.tzinfo)


def load_bookings(now: datetime) -> dict[str, Booking]:
    """Seed bookings with departures as offsets from `now` (IST)."""
    out = {}
    for row in _raw():
        data = dict(row, departure=_departure(row["departure"], now))
        out[row["pnr"]] = Booking.model_validate(data)
    return out


def get_booking(pnr: str, now: datetime) -> Booking | None:
    return load_bookings(now).get(pnr)

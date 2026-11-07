"""Flights and fares. Pure: no I/O, no clock."""

from datetime import date, datetime, time, timedelta
from hashlib import sha256

from app.catalog.models import Booking, Flight, Quote
from app.core.clock import IST

CHANGE_FEE = {"saver": 3000, "flex": 0}
QUOTE_TTL = timedelta(minutes=10)
WINDOWS = {"morning": (5, 12), "afternoon": (12, 17), "evening": (17, 24), "any": (0, 24)}

# route -> (minutes, base fare). Index + 1 gives the flight-number hundreds.
ROUTES: dict[str, tuple[int, int]] = {
    "BLR-DEL": (165, 5200),
    "BOM-DEL": (130, 4800),
    "BLR-BOM": (100, 3900),
    "CCU-BLR": (160, 5600),
    "DEL-CCU": (135, 5000),
    "HYD-DEL": (140, 4900),
}
ROUTE_KEYS = list(ROUTES)
SLOTS = ["06:10", "09:35", "13:20", "17:45", "21:05"]


def _h(text: str) -> int:
    return int(sha256(text.encode()).hexdigest(), 16)


def _make(route_idx: int, slot_idx: int, day: date) -> Flight:
    route = ROUTE_KEYS[route_idx]
    minutes, base = ROUTES[route]
    slot = SLOTS[slot_idx]
    h = _h(f"{route}|{day}|{slot}")
    fare = round(base * (0.8 + 0.6 * (h % 1000) / 1000) / 50) * 50
    sold_out_slot = _h(f"{route}|{day}") % len(SLOTS)
    hh, mm = (int(x) for x in slot.split(":"))
    dep = datetime.combine(day, time(hh, mm), tzinfo=IST)
    flight_no = f"AQ{100 * (route_idx + 1) + slot_idx + 1}"
    origin, destination = route.split("-")
    return Flight(
        id=f"{flight_no}-{day:%Y%m%d}",
        flight_no=flight_no,
        origin=origin,
        destination=destination,
        departure=dep,
        arrival=dep + timedelta(minutes=minutes),
        fare=fare,
        sold_out=slot_idx == sold_out_slot,
    )


def flights_for(origin: str, destination: str, day: date, window: str) -> list[Flight]:
    """Bookable flights on a route and day inside a time window. Sold-out ones are left out."""
    route = f"{origin}-{destination}"
    if route not in ROUTES or window not in WINDOWS:
        return []
    start, end = WINDOWS[window]
    idx = ROUTE_KEYS.index(route)
    flights = [_make(idx, s, day) for s in range(len(SLOTS))]
    return [f for f in flights if not f.sold_out and start <= f.departure.hour < end]


def get_flight(flight_id: str) -> Flight | None:
    try:
        flight_no, ymd = flight_id.split("-")
        num = int(flight_no.removeprefix("AQ"))
        day = datetime.strptime(ymd, "%Y%m%d").date()
    except (ValueError, AttributeError):
        return None
    route_idx, slot_idx = num // 100 - 1, num % 100 - 1
    if not (0 <= route_idx < len(ROUTE_KEYS) and 0 <= slot_idx < len(SLOTS)):
        return None
    return _make(route_idx, slot_idx, day)


def make_quote(booking: Booking, flight: Flight, now: datetime) -> Quote:
    pax = len(booking.passengers)
    fee = CHANGE_FEE[booking.fare_class]
    net = (flight.fare - booking.fare_per_pax) * pax + fee * pax
    qid = "q_" + sha256(f"{booking.pnr}|{flight.id}|{now:%Y%m%d%H%M}".encode()).hexdigest()[:8]
    refund_due = max(-net, 0)
    return Quote(
        id=qid,
        pnr=booking.pnr,
        flight_id=flight.id,
        pax=pax,
        old_fare=booking.fare_per_pax,
        new_fare=flight.fare,
        change_fee_per_pax=fee,
        net=net,
        amount_due=max(net, 0),
        refund_due=refund_due,
        refund_to=booking.payment_method if refund_due else None,
        expires_at=now + QUOTE_TTL,
    )


# Seed bookings are static reference data; other domains read them through the service.
from app.catalog.repository import get_booking, load_bookings  # noqa: E402,F401

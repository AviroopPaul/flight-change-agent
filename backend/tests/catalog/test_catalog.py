from datetime import date, datetime, timedelta

from app.catalog.models import Flight
from app.catalog.repository import get_booking, load_bookings
from app.catalog.service import CHANGE_FEE, flights_for, get_flight, make_quote
from app.core.clock import IST

NOW = datetime(2026, 11, 7, 10, 0, tzinfo=IST)


def flight(fare: int, fid: str = "AQ101-20261213") -> Flight:
    dep = datetime(2026, 12, 13, 6, 10, tzinfo=IST)
    return Flight(
        id=fid, flight_no=fid.split("-")[0], origin="BLR", destination="DEL",
        departure=dep, arrival=dep + timedelta(minutes=165), fare=fare, sold_out=False,
    )


def test_load_bookings_offsets():
    b = load_bookings(NOW)
    assert b["ABC123"].departure == datetime(2026, 11, 12, 7, 5, tzinfo=IST)
    assert b["SON333"].departure == NOW + timedelta(hours=2)
    assert b["PQR456"].passengers == ["ANANYA IYER", "KARTIK IYER"]
    assert b["CNX111"].status == "cancelled"
    assert get_booking("ABC123", NOW).fare_per_pax == 5400
    assert get_booking("NOPE00", NOW) is None


def test_flights_deterministic():
    a = flights_for("BLR", "DEL", date(2026, 12, 13), "any")
    b = flights_for("BLR", "DEL", date(2026, 12, 13), "any")
    assert a == b
    assert a and all(f.id.endswith("-20261213") for f in a)


def test_flights_exclude_sold_out_and_respect_window():
    for offset in range(30):
        day = date(2026, 12, 1) + timedelta(days=offset)
        morning = flights_for("BLR", "DEL", day, "morning")
        assert all(5 <= f.departure.hour < 12 for f in morning)
        everything = flights_for("BLR", "DEL", day, "any")
        assert len(everything) <= 4
        assert not any(f.sold_out for f in everything)
        evening = flights_for("BLR", "DEL", day, "evening")
        assert all(17 <= f.departure.hour < 24 for f in evening)


def test_get_flight_roundtrip():
    f = flights_for("BOM", "DEL", date(2026, 12, 13), "any")[0]
    assert get_flight(f.id) == f
    assert get_flight("garbage") is None


def test_unknown_route_returns_empty():
    assert flights_for("XXX", "YYY", date(2026, 12, 13), "any") == []


def test_quote_saver_pay_more():
    q = make_quote(load_bookings(NOW)["ABC123"], flight(6200), NOW)
    assert (q.net, q.amount_due, q.refund_due) == (3800, 3800, 0)
    assert q.change_fee_per_pax == CHANGE_FEE["saver"] == 3000
    assert q.id.startswith("q_") and len(q.id) == 10


def test_quote_saver_cheaper_still_pays_fee():
    q = make_quote(load_bookings(NOW)["ABC123"], flight(4200), NOW)
    assert q.net == 1800 and q.amount_due == 1800 and q.refund_due == 0


def test_quote_flex_refund():
    q = make_quote(load_bookings(NOW)["FLX789"], flight(7400), NOW)
    assert q.net == -1500
    assert q.refund_due == 1500 and q.amount_due == 0
    assert q.refund_to == "UPI •• kotak"


def test_quote_two_pax():
    q = make_quote(load_bookings(NOW)["PQR456"], flight(6500), NOW)
    assert q.pax == 2
    assert q.net == (6500 - 6100) * 2 + 3000 * 2 == 6800


def test_quote_expiry():
    q = make_quote(load_bookings(NOW)["ABC123"], flight(6200), NOW)
    assert q.expires_at == NOW + timedelta(minutes=10)


def test_quote_id_deterministic_per_minute():
    b = load_bookings(NOW)["ABC123"]
    assert make_quote(b, flight(6200), NOW).id == make_quote(b, flight(6200), NOW + timedelta(seconds=30)).id

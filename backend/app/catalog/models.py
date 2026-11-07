from datetime import datetime
from typing import Literal

from app.core.model import CamelModel


class Booking(CamelModel):
    pnr: str
    status: Literal["confirmed", "cancelled"]
    fare_class: Literal["saver", "flex"]
    passengers: list[str]
    origin: str
    destination: str
    flight_no: str
    departure: datetime
    fare_per_pax: int
    payment_method: str | None = None


class Flight(CamelModel):
    id: str
    flight_no: str
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    fare: int
    sold_out: bool


class Quote(CamelModel):
    id: str
    pnr: str
    flight_id: str
    pax: int
    old_fare: int
    new_fare: int
    change_fee_per_pax: int
    net: int
    amount_due: int
    refund_due: int
    refund_to: str | None = None
    currency: str = "INR"
    expires_at: datetime

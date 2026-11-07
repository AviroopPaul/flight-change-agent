from datetime import datetime
from hashlib import sha256

from fastapi import Request

SESSIONS_PER_IP_PER_HOUR = 10


def client_ip(request: Request) -> str:
    """First X-Forwarded-For entry on Cloud Run, else the socket peer."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd.strip():
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def ip_hash(ip: str, secret: str) -> str:
    return sha256(f"{ip}{secret}".encode()).hexdigest()[:16]


def start_of_day(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """The only place in the app that reads the wall clock."""
    return datetime.now(IST)

from app.sessions.effects import record_summary


def test_summary_speaks_the_date_not_iso():
    """Live test: the agent said 'on 2026-11-12 at 17:45'."""
    rec = {"outcome": "completed", "quote": {"amountDue": 4300},
           "fields": {"selectedFlight": {"value": {"flightNo": "AQ104", "departure": "2026-11-12T17:45:00+05:30"}}}}
    assert record_summary(rec) == ("You're all set. Your new flight is AQ104 on Thursday 12 November 2026 "
                                   "at 17:45. You pay 4,300 rupees.")

"""Outcome rules. Pure."""

from app.sessions.fields import REQUIRED_CHANGE, REQUIRED_REFUND
from app.sessions.models import SessionState


def _missing(state: SessionState, required: list[str]) -> list[str]:
    return [f for f in required if state.fields[f].status != "valid"]


def decide_outcome(state: SessionState, *, idle: bool) -> tuple[str, str] | None:
    """Return (outcome, outcomeReason) or None. optedOut > needsReview > completed > partial."""
    if state.opted_out:
        return "optedOut", "user asked to stop"
    required = REQUIRED_REFUND if state.request_type == "refund" else REQUIRED_CHANGE
    if state.request_type == "refund" and not _missing(state, REQUIRED_REFUND):
        return "needsReview", "refund requested instead of change"
    if idle:
        open_conflicts = [c.field for c in state.conflicts if c.resolution is None]
        if open_conflicts:
            return "needsReview", f"unresolved conflict on {', '.join(open_conflicts)}"
    accepted = (state.fields["fareAcceptance"].value or {}).get("accepted") is True
    if state.request_type == "change" and not _missing(state, REQUIRED_CHANGE) and accepted:
        return "completed", "all required fields valid, fare accepted"
    if idle:
        missing = _missing(state, required)
        if missing:
            return "partial", f"user stopped responding with {', '.join(missing)} missing"
    return None


def is_final(outcome: str) -> bool:
    return outcome != "partial"

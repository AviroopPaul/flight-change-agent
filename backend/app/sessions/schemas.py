from app.core.model import CamelModel


class SessionCreated(CamelModel):
    session_id: str


class SessionView(CamelModel):
    session_id: str
    locked: bool
    outcome: str | None
    call_active: bool
    open_card: dict | None = None

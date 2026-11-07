import hmac

from fastapi import HTTPException, Request


def require_service_token(request: Request) -> None:
    """401 unless `Authorization: Bearer {SERVICE_TOKEN}`."""
    expected = request.app.state.settings.service_token
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    if not expected or not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="unauthorized")

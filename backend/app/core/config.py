from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Every secret comes from the environment only."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = "postgresql://dev:dev@localhost:5433/flight"
    service_token: str = ""
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    groq_api_key: str = ""
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    daily_session_cap: int = 200
    stub_url: str | None = None
    public_url: str = "http://localhost:8080"
    chat_autostart_seconds: float = 20.0
    sweep_on_startup: bool = True

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def effective_stub_url(self) -> str:
        return self.stub_url or f"{self.public_url.rstrip('/')}/stub/records"

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DM Assistant"
    environment: str = "development"  # development | production | test
    public_base_url: str = "http://localhost:8000"
    # The panel; users are sent back here after connecting Instagram.
    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = ["http://localhost:3000"]

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/app"
    redis_url: str = "redis://localhost:6379/0"
    # "arq" (Redis, production) or "inline" (in-process; local dev without Redis, jobs are
    # lost on restart).
    queue_backend: Literal["arq", "inline"] = "arq"

    # Wait this long after a customer's message before replying, so bursts of short
    # messages ("salam" / "in mantoo" / "size 44 dari?") get one combined answer.
    reply_debounce_seconds: float = 5.0

    # JWT signing key and Fernet key for encrypting third-party tokens at rest.
    secret_key: str = _INSECURE_SECRET
    encryption_key: str = ""
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Meta / Instagram API with Instagram Login. These are the *Instagram* app ID and secret
    # shown under Instagram > API setup with Instagram login (not the Facebook app ID).
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_webhook_verify_token: str = ""
    meta_graph_api_version: str = "v23.0"
    # Log outgoing DMs instead of sending them (local testing with the webhook simulator).
    instagram_dry_run: bool = False

    # Any OpenAI-compatible provider (direct or an Iranian gateway).
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.is_production:
            if self.secret_key == _INSECURE_SECRET or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be set to a random value of 32+ chars")
            if not self.encryption_key:
                raise ValueError("ENCRYPTION_KEY must be set in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

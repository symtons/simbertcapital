from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables and the .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"
    shadow_mode: bool = True

    llm_provider: Literal["fake", "openai", "ollama"] = "fake"
    llm_spend_cap_usd: float = Field(default=5.0, ge=0, le=20)
    openai_api_key: SecretStr | None = None

    oanda_env: Literal["practice", "live"] = "practice"
    oanda_api_token: SecretStr | None = None
    oanda_account_id: str | None = None

    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None


def get_settings() -> Settings:
    return Settings()
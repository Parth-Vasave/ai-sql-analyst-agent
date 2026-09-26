"""Application settings, loaded from environment variables (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Databases the analyst can query: a TOML file of [[databases]] entries, or a single
    # DATABASE_URL. Always read-only accounts; accounts that can modify data are refused.
    databases_config: Path | None = None
    database_url: SecretStr | None = None
    # Lets users add databases through the UI/API. Local or self-hosted use only: never
    # enable on a public deployment (it lets anyone make the server connect anywhere).
    allow_ui_connections: bool = False
    profile_time_budget_seconds: float = Field(default=30, gt=0, le=300)

    query_timeout_seconds: float = Field(default=5, gt=0, le=60)
    max_retries: int = Field(default=2, ge=0, le=5)
    max_rows: int = Field(default=1000, ge=1, le=10_000)

    # Any OpenAI-compatible chat-completions endpoint (Groq, Gemini, OpenRouter, Ollama, ...).
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = "llama-3.3-70b-versatile"

    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Application settings, loaded from environment variables (see .env.example)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Connection for the read-only sql_agent role. Never the owner/admin account.
    database_url: SecretStr

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
    return Settings()  # type: ignore[call-arg]  # values come from the environment

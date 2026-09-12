"""Application settings, loaded from the environment (or a .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_name: str = "IntervueX"
    environment: Literal["development", "production", "test"] = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Database ---
    database_url: str = "postgresql+psycopg2://intervuex:intervuex@localhost:5432/intervuex"

    # --- Auth ---
    # Override in production. The app refuses to boot with this value when
    # environment == "production" (see validate_runtime_settings).
    secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- LLM ---
    # "auto" resolves in order: anthropic if ANTHROPIC_API_KEY is set, then groq
    # if GROQ_API_KEY is set, then the offline provider.
    llm_provider: Literal["auto", "anthropic", "groq", "offline"] = "auto"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5"
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_max_tokens: int = 8000

    # --- Groq (OpenAI-compatible endpoint) ---
    groq_api_key: str | None = None
    # Must be a model that supports strict json_schema response formatting;
    # the whole product depends on structured output.
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 90.0

    # --- Embeddings ---
    embedding_provider: Literal["auto", "voyage", "hashing"] = "auto"
    voyage_api_key: str | None = None
    voyage_model: str = "voyage-3.5"
    # Fixed so that switching providers never requires a schema migration.
    embedding_dim: int = 1024

    # --- Vector search ---
    # "auto" probes the database for the pgvector extension at startup.
    vector_backend: Literal["auto", "pgvector", "fallback"] = "auto"

    # --- Documents ---
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 200

    # --- Interview ---
    default_question_count: int = 8

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def validate_runtime_settings(s: Settings = settings) -> None:
    """Fail fast on configuration that is unsafe outside development."""
    if s.environment == "production" and s.secret_key == "dev-secret-change-me":
        raise RuntimeError(
            "SECRET_KEY must be set to a unique value when ENVIRONMENT=production"
        )

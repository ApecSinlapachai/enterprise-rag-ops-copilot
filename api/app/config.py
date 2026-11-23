"""Application configuration via Pydantic BaseSettings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed environment settings for the RAG Copilot & Triage API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Enterprise RAG Ops Copilot API"
    app_version: str = "0.1.0"
    environment: str = "development"

    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/rag_ops"
    )
    gemini_api_key: str = Field(default="your-gemini-api-key-here")
    gemini_chat_model: str = Field(default="gemini-3.8-flash")
    gemini_embed_model: str = Field(default="gemini-embedding-001")
    gemini_embed_dim: int = Field(default=1536, ge=128, le=3072)

    admin_ingest_token: str = Field(default="change-me-local-admin-token")
    cors_origins: str = Field(default="http://localhost:3000")

    rate_limit_per_min: int = Field(default=15, ge=1)
    rate_limit_per_day: int = Field(default=60, ge=1)

    min_vec_similarity: float = Field(default=0.58, ge=-1.0, le=1.0)
    min_fts_rank: float = Field(default=0.08, ge=0.0)
    min_llm_confidence: float = Field(default=0.55, ge=0.0, le=1.0)
    citation_snippet_max_chars: int = Field(default=380, ge=50, le=400)

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()

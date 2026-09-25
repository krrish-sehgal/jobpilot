"""Application configuration.

All configuration is sourced from environment variables (optionally via
a local `.env` file during development). Nothing in this module talks
to a network; it only describes what the rest of the application is
allowed to read. See `.env.example` for the full list of variables a
deployment needs to set.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration, loaded once and cached.

    Every field has a safe, obviously-non-production default so the
    test suite and local tooling can import this module without a
    `.env` file present. Real deployments override every value below
    via environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="JOBPILOT_",
        extra="ignore",
    )

    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="console", description="console | json")

    # Supabase / Postgres
    supabase_url: str = Field(default="https://your-project.supabase.co")
    supabase_service_role_key: str = Field(default="replace-with-service-role-key")
    supabase_anon_key: str = Field(default="replace-with-anon-key")
    database_pool_min_size: int = Field(default=1, ge=1)
    database_pool_max_size: int = Field(default=10, ge=1)

    # LLM provider
    llm_provider: str = Field(default="fake", description="fake | openai | anthropic")
    llm_api_key: str = Field(default="replace-with-llm-api-key")
    llm_chat_model: str = Field(default="gpt-4o-mini")
    llm_embedding_model: str = Field(default="text-embedding-3-small")
    llm_embedding_dimensions: int = Field(default=1536, ge=8)
    llm_request_timeout_seconds: float = Field(default=30.0, gt=0)

    # Object storage (raw scraped postings)
    object_storage_bucket: str = Field(default="jobpilot-raw-postings")
    object_storage_endpoint: str = Field(default="https://storage.example.com")
    object_storage_access_key: str = Field(default="replace-with-access-key")
    object_storage_secret_key: str = Field(default="replace-with-secret-key")

    # Queue (ingestion + enrichment fan-out)
    queue_backend: str = Field(default="memory", description="memory | sqs | redis")
    queue_url: str = Field(default="https://queue.example.com/jobpilot-ingest")
    queue_visibility_timeout_seconds: int = Field(default=60, gt=0)
    queue_max_receive_count: int = Field(default=5, ge=1)

    # Chat / webhook
    webhook_signing_secret: str = Field(default="replace-with-webhook-secret")
    turn_lease_seconds: int = Field(default=45, gt=0)
    agent_max_turns: int = Field(default=6, ge=1, le=20)
    agent_max_tool_calls_per_turn: int = Field(default=4, ge=1, le=20)

    # Ranking weights (must sum to 1.0; validated in search.ranking)
    ranking_weight_semantic: float = Field(default=0.45, ge=0, le=1)
    ranking_weight_recency: float = Field(default=0.15, ge=0, le=1)
    ranking_weight_seniority_fit: float = Field(default=0.20, ge=0, le=1)
    ranking_weight_location_fit: float = Field(default=0.10, ge=0, le=1)
    ranking_weight_completeness: float = Field(default=0.10, ge=0, le=1)

    # Rate limiting (outbound calls to third-party ATS platforms)
    scraper_rate_limit_tokens_per_second: float = Field(default=2.0, gt=0)
    scraper_rate_limit_bucket_size: int = Field(default=10, ge=1)

    # Retry / backoff
    retry_max_attempts: int = Field(default=5, ge=1)
    retry_base_delay_seconds: float = Field(default=0.5, gt=0)
    retry_max_delay_seconds: float = Field(default=20.0, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""

    return Settings()

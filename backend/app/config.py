"""Application configuration, loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM provider (OpenAI-compatible) ---
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    # --- Search provider ---
    tavily_api_key: str = ""
    search_provider: str = "auto"  # auto | tavily | duckduckgo | mock

    # --- Research bounds (cost/latency control) ---
    max_subquestions: int = 4
    max_results_per_query: int = 5
    max_sources_total: int = 12
    max_sources_for_evidence: int = 8
    max_sources_per_domain: int = 3
    max_fetch_chars: int = 6000  # chars of extracted page text kept per source
    max_evidence_chars_per_source: int = 1200  # chars sent to evidence-extraction LLM call
    fetch_timeout_seconds: float = 10.0
    fetch_max_retries: int = 2
    request_concurrency: int = 5

    # --- Storage ---
    database_path: str = "research_agent.db"
    cache_ttl_seconds: int = 3600

    # --- Server ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    environment: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_api_key) and self.search_provider != "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()

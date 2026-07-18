"""Central configuration.

`pydantic-settings` reads values from environment variables (and the `.env` file),
mapping e.g. GEMINI_API_KEY -> gemini_api_key automatically (case-insensitive).
Everything has a sane default so the app boots even before every value is set.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM provider (used from Phase 2 onward) ---
    llm_provider: str = "gemini"            # "gemini" now | "anthropic" once credits unblock
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    # Free-tier reality (verified 2026-07): newest flash (`flash-latest`→3.5) = 20 req/DAY, `pro` = 429,
    # `gemini-2.0-flash` = limit 0 (paid-only). Only `flash-lite` has generous free quota, so all three
    # roles use it here. The multi-agent design is unchanged; Claude haiku/sonnet/opus tiering returns at swap.
    model_classify: str = "gemini-flash-lite-latest"
    model_resolve: str = "gemini-flash-lite-latest"
    model_critic: str = "gemini-flash-lite-latest"

    # --- Infrastructure (service-name URLs inside the docker network) ---
    database_url: str = "postgresql://poc:poc@db:5432/poc"
    tei_url: str = "http://embeddings:80"
    crawl4ai_url: str = "http://crawler:11235"
    crawl4ai_token: str = "poc-token"   # must match CRAWL4AI_API_TOKEN in docker-compose
    mcp_url: str = "http://mcp:9000/mcp"
    embed_dim: int = 384


settings = Settings()

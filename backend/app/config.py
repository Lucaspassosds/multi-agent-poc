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
    mcp_url: str = "http://mcp:9000/mcp"
    embed_dim: int = 384

    # --- Cost attribution (Phase 6 observability) ---
    # $ per 1M (input, output) tokens — published list price, keyed by model id. This is what the
    # provider WOULD bill on a paid tier; the Gemini free tier actually bills $0 (same honesty
    # already used by /llm/cache-demo). Add Claude model ids here when LLM_PROVIDER swaps.
    model_costs: dict[str, tuple[float, float]] = {
        "gemini-flash-lite-latest": (0.10, 0.40),
    }
    default_model_cost: tuple[float, float] = (0.10, 0.40)  # fallback for an unlisted model id

    # --- Langfuse (Phase D observability, augmentative) ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    # --- Phase D depth knobs ---
    max_revisions: int = 2                # bounded revise loop cap (critique node)
    rerank_enabled: bool = True           # LLM-rerank over the fused top-k
    chaos_inject_429: int = 0             # default synthetic-429 injections per LLM call (0 = off)
    cost_budget_usd: float = 0.05         # per-run cost breach threshold (list-price proxy)
    latency_budget_ms: int = 60000        # per-run latency breach threshold
    regression_tolerance: float = 0.05    # allowed metric drop vs baseline before the gate fails


settings = Settings()

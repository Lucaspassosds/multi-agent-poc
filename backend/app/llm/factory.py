"""Provider factory — picks the implementation from LLM_PROVIDER (one place to swap)."""
from functools import lru_cache

from app.config import settings
from app.llm.base import LLMProvider


@lru_cache
def get_provider() -> LLMProvider:
    if settings.llm_provider == "gemini":
        from app.llm.gemini import GeminiProvider
        return GeminiProvider()
    if settings.llm_provider == "anthropic":
        # Added when Anthropic credits unblock; the interface stays identical.
        raise NotImplementedError("Anthropic provider not implemented yet (see spec 03).")
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")

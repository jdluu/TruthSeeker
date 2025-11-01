"""Application settings and configuration management."""

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv


class Settings:
    """Application configuration loaded from environment variables."""

    def __init__(self) -> None:
        """Load environment variables from .env file."""
        load_dotenv()

    @property
    def synthetic_api_key(self) -> Optional[str]:
        """Synthetic.new API key for LLM access."""
        return os.getenv("SYNTHETIC_API_KEY")

    @property
    def brave_api_key(self) -> Optional[str]:
        """Brave Search API key."""
        return os.getenv("BRAVE_API_KEY")

    @property
    def llm_model(self) -> str:
        """LLM model identifier."""
        return os.getenv("LLM_MODEL", "hf:mistralai/Mistral-7B-Instruct-v0.3")

    @property
    def http_timeout_seconds(self) -> float:
        """HTTP client timeout in seconds."""
        return float(os.getenv("HTTP_TIMEOUT_SECONDS", "20.0"))

    @property
    def search_cache_ttl(self) -> int:
        """Search result cache TTL in seconds."""
        return int(os.getenv("SEARCH_CACHE_TTL", "300"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance (singleton pattern)."""
    return Settings()


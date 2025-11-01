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
    def deepseek_api_key(self) -> Optional[str]:
        """DeepSeek API key for LLM access."""
        return os.getenv("DEEPSEEK_API_KEY")

    @property
    def brave_api_key(self) -> Optional[str]:
        """Brave Search API key."""
        return os.getenv("BRAVE_API_KEY")

    @property
    def llm_model(self) -> str:
        """LLM model identifier. Uses DeepSeek's default chat model."""
        return "deepseek-chat"

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


from __future__ import annotations

from typing import Optional
try:
    # Prefer Pydantic/typed Deps if refactor package is available
    from src.truthseeker.models import SearchResult  # noqa: F401
except Exception:
    pass

from dataclasses import dataclass
from httpx import AsyncClient


@dataclass
class Deps:
    """
    Lightweight dependency container used by pydantic-ai Agent tooling.
    Kept as a dataclass for compatibility with pydantic-ai's deps_type usage.
    """
    client: AsyncClient
    brave_api_key: Optional[str] = None

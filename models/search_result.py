from typing import Any

# Re-export Pydantic SearchResult model when available to centralize schema and validation.
# This keeps backward compatibility for modules that import models.search_result.SearchResult.
try:
    from src.truthseeker.models import SearchResult as PydanticSearchResult  # type: ignore
except Exception:
    PydanticSearchResult = None  # type: ignore

if PydanticSearchResult is not None:
    SearchResult = PydanticSearchResult  # type: ignore
else:
    # Fallback dataclass for environments where the refactor package is not importable.
    from dataclasses import dataclass

    @dataclass
    class SearchResult:
        title: str
        description: str = ""
        url: str = ""
        query_time: float = 0.0

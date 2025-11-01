"""Brave Search API client implementation."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from httpx import AsyncClient, HTTPStatusError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ...domain.models import SearchResult

logger = logging.getLogger(__name__)


class BraveSearchClient:
    """Brave Search API client with retries, backoff, and caching.

    Features:
        - Automatic retries with exponential backoff
        - In-memory TTL cache
        - Optional file-backed cache for persistence

    Usage:
        ```python
        client = BraveSearchClient(
            api_key="your-key",
            http_client=async_client,
            cache_ttl=300,
            cache_file="cache.json"
        )
        results = await client.search("query", count=5)
        ```
    """

    BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self,
        api_key: Optional[str],
        http_client: AsyncClient,
        cache_ttl: int = 300,
        cache_file: Optional[Path] = None,
    ) -> None:
        """Initialize Brave Search client.

        Args:
            api_key: Brave Search API key. If None, returns placeholder results.
            http_client: HTTP client for making requests.
            cache_ttl: Cache TTL in seconds. Defaults to 300.
            cache_file: Optional path to cache file for persistence.
        """
        self.api_key = api_key
        self._client = http_client
        self.cache_ttl = int(cache_ttl)
        self._cache: Dict[str, Tuple[float, List[SearchResult]]] = {}
        self.cache_file = Path(cache_file) if cache_file else None

        if self.cache_file:
            try:
                self._load_cache_file()
            except Exception:
                logger.exception("Failed to load cache file; continuing with empty cache.")

    def _cache_key(self, query: str, count: int, search_lang: str) -> str:
        """Generate normalized cache key for a query."""
        return f"{query.strip().lower()}::count={count}::lang={search_lang}"

    def _load_cache_file(self) -> None:
        """Load cache from file if it exists."""
        if not self.cache_file or not self.cache_file.exists():
            return
        try:
            raw = json.loads(self.cache_file.read_text(encoding="utf-8"))
            now = time.time()
            for k, v in raw.items():
                ts = float(v.get("ts", 0))
                items = v.get("results", []) or []
                results = []
                for itm in items:
                    try:
                        results.append(SearchResult(**itm))
                    except Exception:
                        continue
                # Only load if not already expired
                if now - ts <= self.cache_ttl:
                    self._cache[k] = (ts, results)
        except Exception:
            logger.exception("Error loading cache file %s", self.cache_file)

    def _save_cache_file(self) -> None:
        """Save cache to file (best-effort)."""
        if not self.cache_file:
            return
        payload: Dict[str, Any] = {}
        for k, (ts, results) in self._cache.items():
            payload[k] = {
                "ts": ts,
                "results": [r.model_dump() for r in results],
            }
        try:
            self.cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("Error saving cache file %s", self.cache_file)

    def _get_from_cache(self, key: str) -> Optional[List[SearchResult]]:
        """Retrieve cached results if available and not expired."""
        entry = self._cache.get(key)
        if not entry:
            return None
        ts, results = entry
        if time.time() - ts > self.cache_ttl:
            try:
                del self._cache[key]
            except KeyError:
                pass
            return None
        return results

    def _set_cache(self, key: str, results: List[SearchResult]) -> None:
        """Store results in cache."""
        self._cache[key] = (time.time(), results)
        if self.cache_file:
            try:
                self._save_cache_file()
            except Exception:
                logger.exception("Failed to persist cache file.")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def search(
        self, query: str, count: int = 5, search_lang: str = "en"
    ) -> List[SearchResult]:
        """Perform a Brave web search with caching.

        Args:
            query: Search query string.
            count: Number of results to return. Defaults to 5.
            search_lang: Search language code. Defaults to "en".

        Returns:
            List of SearchResult objects.

        Raises:
            HTTPStatusError: If the API request fails.
        """
        start = time.time()
        cache_key = self._cache_key(query, count, search_lang)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            logger.debug("Cache hit for query '%s' (count=%d lang=%s)", query, count, search_lang)
            return cached

        if not self.api_key:
            # Return placeholder when API key is not configured
            placeholder = [
                SearchResult(
                    title="Test Result",
                    description="This is a test web search result. Please provide a Brave API key to get real search results.",
                    url="https://example.com",
                    query_time=0.0,
                )
            ]
            self._set_cache(cache_key, placeholder)
            return placeholder

        headers: Dict[str, str] = {
            "X-Subscription-Token": self.api_key,
            "Accept": "application/json",
        }

        params = {
            "q": query,
            "count": count,
            "text_decorations": True,
            "search_lang": search_lang,
        }

        try:
            resp = await self._client.get(self.BASE_URL, params=params, headers=headers)
            resp.raise_for_status()
            data: Dict[str, Any] = resp.json()
        except HTTPStatusError as e:
            logger.warning("HTTP error from Brave Search: %s", str(e))
            raise
        except Exception as e:
            logger.error("Error calling Brave Search API", exc_info=True)
            raise

        query_time = time.time() - start
        results: List[SearchResult] = []

        for item in data.get("web", {}).get("results", []):
            try:
                results.append(
                    SearchResult(
                        title=item.get("title", "No title"),
                        description=item.get("description", "No description available"),
                        url=item.get("url", "https://example.com"),
                        query_time=query_time,
                    )
                )
            except Exception:
                logger.warning("Skipping malformed search result item", extra={"item": item})
                continue

        try:
            self._set_cache(cache_key, results)
        except Exception:
            logger.exception("Failed to update cache for query '%s'", query)

        return results


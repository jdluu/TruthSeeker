from typing import Any, List, Dict, Optional
import time
import logfire

from httpx import AsyncClient

# Use the new BraveSearchClient abstraction when available
try:
    from src.truthseeker.search.client import BraveSearchClient
except Exception:
    BraveSearchClient = None  # type: ignore


async def search_web_direct(client: AsyncClient, brave_api_key: Optional[str], web_query: str) -> List[Dict[str, Any]]:
    """
    Wrapper for performing a web search. Prefer the BraveSearchClient abstraction
    (provides retries/backoff and typed results). Falls back to a minimal error
    response when the client or API key is unavailable.
    """
    start_time = time.time()

    if not brave_api_key and BraveSearchClient is None:
        return [{
            "title": "Test Result",
            "description": "This is a test web search result. Please provide a Brave API key to get real search results.",
            "url": "#",
            "query_time": 0.0
        }]

    if BraveSearchClient is not None:
        try:
            bclient = BraveSearchClient(api_key=brave_api_key, client=client)
            results = await bclient.search(web_query, count=5)
            # Convert Pydantic models to plain dicts for backward compatibility
            return [r.dict() for r in results]
        except Exception as e:
            logfire.error('Error performing Brave Search', error=str(e))
            return [{
                "title": "Error",
                "description": "Error performing web search. Please try again.",
                "url": "#",
                "query_time": 0.0
            }]

    # Fallback (shouldn't normally be used because BraveSearchClient is present)
    return [{
        "title": "Error",
        "description": "Search client not available.",
        "url": "#",
        "query_time": 0.0
    }]

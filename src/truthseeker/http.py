from typing import Optional
from functools import lru_cache

from httpx import AsyncClient, Limits, Timeout


def get_async_client(timeout_seconds: float = 20.0) -> AsyncClient:
    """
    Return a cached AsyncClient with sensible defaults.
    Call client.aclose() at shutdown if necessary.
    """
    return _cached_client(timeout_seconds)


@lru_cache(maxsize=1)
def _cached_client(timeout_seconds: float) -> AsyncClient:
    timeout = Timeout(timeout_seconds)
    limits = Limits(max_keepalive_connections=10, max_connections=50)
    client: AsyncClient = AsyncClient(timeout=timeout, limits=limits)
    return client
"""HTTP client factory with sensible defaults."""

from functools import lru_cache
from typing import Optional

from httpx import AsyncClient, Limits, Timeout


class HTTPClientFactory:
    """Factory for creating HTTP clients with consistent configuration."""

    @staticmethod
    def create(timeout_seconds: float = 20.0) -> AsyncClient:
        """Create a new AsyncClient with sensible defaults.

        Args:
            timeout_seconds: Request timeout in seconds.

        Returns:
            Configured AsyncClient instance.
        """
        timeout = Timeout(timeout_seconds)
        limits = Limits(max_keepalive_connections=10, max_connections=50)
        return AsyncClient(timeout=timeout, limits=limits)


@lru_cache(maxsize=1)
def _cached_client(timeout_seconds: float) -> AsyncClient:
    """Internal cached client factory."""
    return HTTPClientFactory.create(timeout_seconds)


def get_async_client(timeout_seconds: Optional[float] = None) -> AsyncClient:
    """Get a cached AsyncClient with sensible defaults.

    Args:
        timeout_seconds: Optional timeout override. If None, uses default of 20.0.

    Returns:
        Cached AsyncClient instance.

    Note:
        Call client.aclose() at shutdown if necessary.
    """
    timeout = timeout_seconds if timeout_seconds is not None else 20.0
    return _cached_client(timeout)


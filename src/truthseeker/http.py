"""Legacy HTTP client import - redirects to infrastructure layer."""

# Backward compatibility: redirect old imports to new infrastructure layer
from .infrastructure.http.client import get_async_client

__all__ = ["get_async_client"]

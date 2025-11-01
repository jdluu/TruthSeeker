"""Legacy search imports - redirects to infrastructure layer."""

# Backward compatibility
from ..infrastructure.search.brave_client import BraveSearchClient

__all__ = ["BraveSearchClient"]


"""Legacy models import - redirects to domain layer for backward compatibility."""

# Backward compatibility: redirect old imports to new domain layer
from .domain.models import (
    AnalysisResult,
    Reference,
    SearchResult,
    Verdict,
)

__all__ = ["AnalysisResult", "Reference", "SearchResult", "Verdict"]

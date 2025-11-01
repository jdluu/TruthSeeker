"""Core domain models for the fact-checking application."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, Field, field_validator


class Verdict(str, Enum):
    """Represents the truthfulness verdict of a statement."""

    TRUE = "TRUE"
    MOSTLY_TRUE = "MOSTLY_TRUE"
    PARTIALLY_TRUE = "PARTIALLY_TRUE"
    MOSTLY_FALSE = "MOSTLY_FALSE"
    FALSE = "FALSE"
    UNVERIFIABLE = "UNVERIFIABLE"


class Reference(BaseModel):
    """A reference source used in fact-checking analysis."""

    title: str
    url: HttpUrl


class SearchResult(BaseModel):
    """Result from a web search query."""

    title: str
    description: str = ""
    url: HttpUrl
    query_time: float = 0.0


class AnalysisResult(BaseModel):
    """Complete fact-checking analysis result with verdict and evidence."""

    verdict: Verdict
    explanation: str
    context: Optional[str] = None
    references: List[Reference] = Field(default_factory=list)
    search_time: float = 0.0
    analysis_time: float = 0.0

    @field_validator("explanation")
    @classmethod
    def explanation_not_empty(cls, v: str) -> str:
        """Ensure explanation is not empty."""
        if not v or not v.strip():
            raise ValueError("explanation must not be empty")
        return v


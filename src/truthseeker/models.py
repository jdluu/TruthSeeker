from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, HttpUrl, Field, validator


class Verdict(str, Enum):
    TRUE = "TRUE"
    MOSTLY_TRUE = "MOSTLY_TRUE"
    PARTIALLY_TRUE = "PARTIALLY_TRUE"
    MOSTLY_FALSE = "MOSTLY_FALSE"
    FALSE = "FALSE"
    UNVERIFIABLE = "UNVERIFIABLE"


class Reference(BaseModel):
    title: str
    url: HttpUrl


class SearchResult(BaseModel):
    title: str
    description: str = ""
    url: HttpUrl
    query_time: float = 0.0


class AnalysisResult(BaseModel):
    verdict: Verdict
    explanation: str
    context: Optional[str] = None
    references: List[Reference] = Field(default_factory=list)
    search_time: float = 0.0
    analysis_time: float = 0.0

    @validator("explanation")
    def explanation_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("explanation must not be empty")
        return v
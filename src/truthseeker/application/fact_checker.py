"""Fact-checking service - Core business logic."""

import logging
import time
from typing import List

from ..domain.models import AnalysisResult, SearchResult
from ..infrastructure.llm.client import LLMClient
from ..infrastructure.llm.parser import LLMResponseParser, llm_system_prompt
from ..infrastructure.search.brave_client import BraveSearchClient

logger = logging.getLogger(__name__)


class FactCheckerService:
    """Service for performing fact-checking analysis.

    Coordinates search and LLM analysis to produce fact-checking results.
    """

    def __init__(
        self,
        search_client: BraveSearchClient,
        llm_client: LLMClient,
        response_parser: LLMResponseParser,
    ) -> None:
        """Initialize fact-checking service.

        Args:
            search_client: Client for performing web searches.
            llm_client: Client for LLM interactions.
            response_parser: Parser for LLM responses.
        """
        self.search_client = search_client
        self.llm_client = llm_client
        self.response_parser = response_parser

    def _format_search_results(self, results: List[SearchResult]) -> str:
        """Format search results into a string for LLM analysis.

        Args:
            results: List of search results.

        Returns:
            Formatted string representation.
        """
        return "\n---\n".join(
            [f"[Source: {r.title}]\nURL: {r.url}\n{r.description}\n" for r in results]
        )

    async def fact_check(
        self, statement: str, search_query_prefix: str = "fact check"
    ) -> AnalysisResult:
        """Perform fact-checking analysis on a statement.

        Args:
            statement: Statement to fact-check.
            search_query_prefix: Prefix for search query. Defaults to "fact check".

        Returns:
            AnalysisResult with verdict, explanation, and references.
        """
        # Step 1: Search the web
        search_start = time.time()
        search_query = f"{search_query_prefix} {statement}"
        search_results = await self.search_client.search(search_query, count=5)
        search_time = time.time() - search_start

        # Step 2: Format results for LLM
        formatted_results = self._format_search_results(search_results)

        # Step 3: Analyze with LLM
        analysis_start = time.time()
        system_prompt = llm_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Statement: {statement}\n\nEvidence:\n{formatted_results}",
            },
        ]

        try:
            llm_response = await self.llm_client.chat_completion(messages)
            analysis_result = self.response_parser.parse(llm_response)
        except Exception as e:
            logger.exception("Error during LLM analysis")
            from ..domain.models import Verdict

            analysis_result = AnalysisResult(
                verdict=Verdict.UNVERIFIABLE,
                explanation=f"Error during analysis: {str(e)}",
                context=None,
                references=[],
                search_time=0.0,
                analysis_time=0.0,
            )

        analysis_time = time.time() - analysis_start

        # Step 4: Populate timings
        analysis_result.search_time = search_time
        analysis_result.analysis_time = analysis_time

        return analysis_result


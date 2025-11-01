"""Fact-checking service - Core business logic."""

import json
import logging
import time
from typing import Any, List

from ..domain.models import AnalysisResult, SearchResult
from ..infrastructure.llm.client import LLMClient
from ..infrastructure.llm.parser import LLMResponseParser
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

    def _get_search_tool_definition(self) -> Any:
        """Get function calling tool definition for Brave search.

        Returns:
            Tool definition dictionary for function calling.
        """
        return {
            "type": "function",
            "function": {
                "name": "brave_search",
                "description": "Search the web using Brave Search to find evidence and information about a statement or claim. Use this when you need to fact-check a statement by finding relevant sources and evidence.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find information about the statement. Include key facts or claims from the statement in the query.",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of search results to return. Default is 5.",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    async def _handle_brave_search(
        self, query: str, count: int = 5
    ) -> str:
        """Handle Brave search function call.

        Args:
            query: Search query string.
            count: Number of results to return.

        Returns:
            JSON string of search results.
        """
        try:
            search_start = time.time()
            results = await self.search_client.search(query, count=count)
            search_time = time.time() - search_start
            
            formatted = self._format_search_results(results)
            # Return both formatted string and structured data
            # Convert Pydantic models to dict, ensuring URLs are strings
            return json.dumps(
                {
                    "formatted": formatted,
                    "results": [
                        {
                            "title": r.title,
                            "url": str(r.url),  # Convert HttpUrl to string
                            "description": r.description,
                        }
                        for r in results
                    ],
                    "search_time": search_time,
                },
                indent=2,
            )
        except Exception as e:
            logger.exception("Error in brave_search tool call")
            return json.dumps({"error": str(e)})

    async def fact_check(
        self, statement: str, search_query_prefix: str = "fact check"
    ) -> AnalysisResult:
        """Perform fact-checking analysis on a statement using function calling.

        Args:
            statement: Statement to fact-check.
            search_query_prefix: Prefix for search query (used if LLM doesn't use function calling). Defaults to "fact check".

        Returns:
            AnalysisResult with verdict, explanation, and references.
        """
        # Track timing
        search_time = 0.0
        analysis_start = time.time()

        # Setup function calling
        tools = [self._get_search_tool_definition()]
        tool_handlers = {
            "brave_search": self._handle_brave_search,
        }

        # System prompt for function calling approach
        system_prompt = """
You are an expert fact-checker. Your task is to analyze statements and determine their truthfulness.

When a user provides a statement to fact-check:
1. Use the brave_search function to search for evidence and information about the statement
2. Analyze the search results carefully
3. Return a single valid JSON object (only JSON) that conforms to the following schema:

{
  "verdict": "TRUE|MOSTLY_TRUE|PARTIALLY_TRUE|MOSTLY_FALSE|FALSE|UNVERIFIABLE",
  "explanation": "A detailed explanation with inline citation markers like [1], [2], ... referencing the search results",
  "context": "Optional additional context or nuance",
  "references": [
    { "title": "Source title", "url": "https://..." },
    ...
  ],
  "search_time": 0.0,
  "analysis_time": 0.0
}

- Only return JSON (no surrounding text)
- Use standard HTTP/HTTPS URLs for references from the search results
- Base your verdict on the evidence found in the search results
- If insufficient evidence is found, use UNVERIFIABLE verdict
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Please fact-check this statement: {statement}",
            },
        ]

        try:
            # Use function calling - the LLM will decide when to search
            llm_response = await self.llm_client.chat_completion_with_tools(
                messages=messages,
                tools=tools,
                tool_handlers=tool_handlers,
                max_iterations=5,
            )
            analysis_result = self.response_parser.parse(llm_response)

            # Note: search_time is tracked within the tool handler, but we approximate it
            # For more accurate timing, we'd need to track it in the handler
            search_time = 0.0  # Approximated - actual search happens in tool call

        except Exception as e:
            logger.exception("Error during LLM analysis with function calling")
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

        # Populate timings
        analysis_result.search_time = search_time
        analysis_result.analysis_time = analysis_time

        return analysis_result


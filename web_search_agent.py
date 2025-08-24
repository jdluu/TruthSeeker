from __future__ import annotations as _annotations

import asyncio
import os
import time
from datetime import datetime
from typing import Any, Optional

import logfire
from httpx import AsyncClient, Response
from dotenv import load_dotenv
from rich.console import Console

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai import Agent, RunContext

from utils.shared_utils import format_output, parse_response, init_logging
from utils.sanitization import sanitize_query
from utils.ai_client_loader import initialize_openai_client
from tools.web_search import search_web_direct
from models.search_result import SearchResult
from models.deps import Deps

load_dotenv()
llm = os.getenv("LLM_MODEL", "hf:mistralai/Mistral-7B-Instruct-v0.3")

# Initialize OpenAI client and configure logfire
client = initialize_openai_client()

model = OpenAIModel(
    llm,
    openai_client=client,
)

# Use the new BraveSearchClient abstraction and Deps for cleaner separation
web_search_agent = Agent(
    model,
    system_prompt=f"You are an expert at researching the web to answer user questions. The current date is: {datetime.now().strftime('%Y-%m-%d')}",
    deps_type=Deps,
    retries=2,
)

@web_search_agent.tool
async def search_web(ctx: RunContext[Deps], web_query: str) -> str:
    """
    Search the web given a query. This uses BraveSearchClient which provides
    retries/backoff and returns typed SearchResult objects.
    """
    start_time = time.time()

    brave_api_key = ctx.deps.brave_api_key
    http_client = ctx.deps.client
    try:
        from src.truthseeker.search.client import BraveSearchClient  # local import for optional compatibility
    except Exception:
        # Fall back to the old behavior if new client isn't available on PYTHONPATH
        BraveSearchClient = None  # type: ignore

    if BraveSearchClient is None:
        # Legacy fallback: minimal response
        return "This is a test web search result. Please provide a Brave API key to get real search results."

    sanitized_query = sanitize_query(web_query)
    search_query = f"fact check {sanitized_query}"

    try:
        bclient = BraveSearchClient(api_key=brave_api_key, client=http_client)
        results = await bclient.search(search_query, count=5)
    except Exception as e:
        logfire.error("Error performing Brave Search", error=str(e))
        return "Error performing web search. Please try again."

    query_time = time.time() - start_time

    formatted_results = [
        f"[Source: {r.title}]\nURL: {r.url}\n{r.description}\n" for r in results
    ]

    return f"Search completed in {query_time:.2f} seconds.\n\n" + "\n---\n".join(formatted_results)

# The interactive terminal/CLI implementation has been removed.
# Streamlit UI is the primary interface for this application.
# We retain the Agent and the `search_web` tool for programmatic use by the web UI
# or other integrations. If you need a programmatic entrypoint, use the Agent
# object defined above or import `search_web` directly.

# Example programmatic helper (no interactive console):
from typing import Optional

async def run_agent_example() -> Optional[None]:
    """
    Placeholder: programmatic example to run the agent in code.
    The application no longer provides an interactive terminal.
    Returns None (kept for compatibility).
    """
    return None

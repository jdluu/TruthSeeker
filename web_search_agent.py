from __future__ import annotations as _annotations

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import re

import logfire
from devtools import debug
from httpx import AsyncClient, Response
from dotenv import load_dotenv
from rich.console import Console

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai import Agent, ModelRetry, RunContext

from shared_utils import format_output, parse_response, init_logging

load_dotenv()
llm = os.getenv('LLM_MODEL', 'hf:mistralai/Mistral-7B-Instruct-v0.3')

# Initialize OpenAI client and configure logfire
client = AsyncOpenAI(
    base_url='https://glhf.chat/api/openai/v1',
    api_key=os.getenv('GLHF_API_KEY')
)

logfire.configure(send_to_logfire='if-token-present')
logfire.instrument_openai(client)

model = OpenAIModel(
    llm,
    openai_client=client,
)

@dataclass
class SearchResult:
    title: str
    description: str
    url: str
    query_time: float

@dataclass
class Deps:
    client: AsyncClient
    brave_api_key: str | None

web_search_agent = Agent(
    model,
    system_prompt=f'You are an expert at researching the web to answer user questions. The current date is: {datetime.now().strftime("%Y-%m-%d")}',
    deps_type=Deps,
    retries=2
)

def sanitize_query(query: str) -> str:
    """Sanitize the search query to prevent injection attacks."""
    sanitized = re.sub(r'[^\w\s-]', '', query)
    return sanitized[:500]

@web_search_agent.tool
async def search_web(
    ctx: RunContext[Deps], web_query: str
) -> str:
    """Search the web given a query defined to answer the user's question."""
    start_time = time.time()
    
    if ctx.deps.brave_api_key is None:
        return "This is a test web search result. Please provide a Brave API key to get real search results."

    sanitized_query = sanitize_query(web_query)
    search_query = f"fact check {sanitized_query}"

    headers: dict[str, str] = {
        'X-Subscription-Token': ctx.deps.brave_api_key,
        'Accept': 'application/json',
    }
    
    try:
        r: Response = await ctx.deps.client.get(
            'https://api.search.brave.com/res/v1/web/search',
            params={
                'q': search_query,
                'count': 5,
                'text_decorations': True,
                'search_lang': 'en'
            },
            headers=headers
        )
        r.raise_for_status()
        data: dict[str, Any] = r.json()
    except Exception as e:
        logfire.error('Error calling Brave API', error=str(e))
        return "Error performing web search. Please try again."

    query_time = time.time() - start_time
    results: list[SearchResult] = []
    
    for web_result in data.get('web', {}).get('results', []):
        results.append(SearchResult(
            title=web_result.get('title', ''),
            description=web_result.get('description', ''),
            url=web_result.get('url', ''),
            query_time=query_time
        ))
    
    formatted_results = [
        f"[Source: {result.title}]\n"
        f"URL: {result.url}\n"
        f"{result.description}\n"
        for result in results
    ]
    
    return f"Search completed in {query_time:.2f} seconds.\n\n" + "\n---\n".join(formatted_results)

async def search_web_direct(client: AsyncClient, brave_api_key: str | None, web_query: str) -> list[dict]:
    """Search the web given a query defined to answer the user's question."""
    start_time = time.time()
    
    if brave_api_key is None:
        return [{
            "title": "Test Result",
            "description": "This is a test web search result. Please provide a Brave API key to get real search results.",
            "url": "#"
        }]

    headers: dict[str, str] = {
        'X-Subscription-Token': brave_api_key,
        'Accept': 'application/json',
    }
    
    try:
        r: Response = await client.get(
            'https://api.search.brave.com/res/v1/web/search',
            params={
                'q': web_query,
                'count': 5,
                'text_decorations': True,
                'search_lang': 'en'
            },
            headers=headers
        )
        r.raise_for_status()
        data: dict[str, Any] = r.json()
    except Exception as e:
        logfire.error('Error calling Brave API', error=str(e))
        return [{
            "title": "Error",
            "description": "Error performing web search. Please try again.",
            "url": "#"
        }]

    query_time = time.time() - start_time
    results = []
    
    for web_result in data.get('web', {}).get('results', []):
        results.append({
            "title": web_result.get('title', 'No title'),
            "description": web_result.get('description', 'No description available'),
            "url": web_result.get('url', '#'),
            "query_time": query_time
        })
    
    return results

async def main():
    init_logging()
    console = Console()
    
    async with AsyncClient() as http_client:
        brave_api_key = os.getenv('BRAVE_API_KEY', None)
        
        console.print("\n[bold cyan]🔍 AI Fact Checker[/bold cyan]")
        console.print("This tool helps verify statements by searching the web and using AI analysis.\n")
        
        while True:
            statement = console.input("[bold green]Enter a statement to fact-check[/bold green] (or 'quit' to exit): ")
            
            if statement.lower() in ['quit', 'exit', 'q']:
                console.print("\n[bold cyan]Thank you for using AI Fact Checker![/bold cyan]")
                break
            
            with console.status("[bold green]Searching the web...") as status:
                search_start = time.time()
                raw_search_results = await search_web_direct(http_client, brave_api_key, f"fact check {statement}")
                search_time = time.time() - search_start
                
                status.update("[bold yellow]Analyzing evidence...")
                analysis_start = time.time()
                
                system_prompt = """You are a fact-checking expert. Analyze the following statement and evidence, then provide your analysis in this exact format:
                
                <verdict>TRUE/FALSE/PARTIALLY TRUE/UNVERIFIABLE</verdict>
                
                <explanation>
                Detailed explanation with citations [1], [2], etc.
                </explanation>
                
                <context>
                Important context or nuance with citations [1], [2], etc.
                </context>
                
                <references>
                1. Source Name - URL
                2. Source Name - URL
                </references>"""
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Statement: {statement}\n\nEvidence:\n{raw_search_results}"}
                ]
                
                completion = await client.chat.completions.create(
                    model=llm,
                    messages=messages
                )
                
                analysis_time = time.time() - analysis_start
                total_time = search_time + analysis_time
                
                verdict, explanation, context, ref_list = parse_response(
                    completion.choices[0].message.content
                )
                
                verdict_panel, explanation_panel, context_panel, ref_table = format_output(
                    verdict, explanation, context, ref_list
                )
                
                console.print("\n[bold cyan]Results:[/bold cyan]")
                console.print(f"[italic]Search completed in {search_time:.2f}s, Analysis in {analysis_time:.2f}s (Total: {total_time:.2f}s)[/italic]\n")
                
                console.print(verdict_panel)
                console.print(explanation_panel)
                if context_panel:
                    console.print(context_panel)
                console.print(ref_table)
                
                console.print("\n" + "="*80 + "\n")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[bold red]Program terminated by user.[/bold red]")
    except Exception as e:
        print(f"\n[bold red]An error occurred: {str(e)}[/bold red]")

import time
import logfire

from httpx import AsyncClient, Response

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

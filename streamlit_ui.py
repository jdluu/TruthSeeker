
from datetime import datetime
import streamlit as st
import asyncio
import os
 
import time
from typing import Any, List, Tuple
 
import html
import json
import base64

from pydantic_ai.messages import ModelTextResponse, UserPrompt

from utils.generate_pdf import generate_pdf

from utils.ai_client_loader import initialize_openai_client
from utils.sanitization import sanitize_html
# Use the new http client factory and BraveSearchClient abstraction
from src.truthseeker.http import get_async_client
from src.truthseeker.search.client import BraveSearchClient
from src.truthseeker.llm.parser import llm_system_prompt, parse_llm_json
from src.truthseeker.models import AnalysisResult

# Page configuration and styling
st.set_page_config(
    page_title="AI Fact Checker",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for responsiveness
st.markdown("""
<style>
    /* Responsive container */
    .main > div {
        max-width: 1200px;
        margin: 0 auto;
        padding: 1rem;
    }
    
    /* Responsive text */
    @media (max-width: 768px) {
        .stMarkdown, .stText {
            font-size: 14px;
        }
        h1 {
            font-size: 24px !important;
        }
        h2 {
            font-size: 20px !important;
        }
        h3 {
            font-size: 18px !important;
        }
    }
    
    /* Chat container */
    .stChatMessage {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        max-width: 100%;
        word-wrap: break-word;
    }
    
    /* Links */
    a {
        color: #FF4B4B;
        text-decoration: none;
    }
    a:hover {
        text-decoration: underline;
    }
    
    /* Verdict styling */
    .verdict {
        font-weight: bold;
        padding: 0.5rem;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
    .verdict.true { background-color: #28a745; color: white; }
    .verdict.false { background-color: #dc3545; color: white; }
    .verdict.partial { background-color: #ffc107; color: black; }
    .verdict.unverifiable { background-color: #6c757d; color: white; }
</style>
""", unsafe_allow_html=True)

# Load environment variables and initialize clients
@st.cache_resource
def init_clients() -> Tuple[Any, str]:
    llm = os.getenv("LLM_MODEL", "hf:mistralai/Mistral-7B-Instruct-v0.3")
    client = initialize_openai_client()
    return client, llm
 
client, llm = init_clients()

def display_verdict(verdict: Any, column: Any) -> None:
    """Safely display the verdict with proper styling."""
    raw = verdict.value if hasattr(verdict, "value") else str(verdict)
    v = html.escape(raw.upper())
    cls_map = {
        "TRUE": "true",
        "MOSTLY_TRUE": "partial",
        "PARTIALLY_TRUE": "partial",
        "MOSTLY_FALSE": "false",
        "FALSE": "false",
        "UNVERIFIABLE": "unverifiable",
    }
    css_class = cls_map.get(v, "unverifiable")
    safe_html = f'<div class="verdict {css_class}">{v}</div>'
    column.markdown(safe_html, unsafe_allow_html=True)

def display_explanation(explanation: str, column: Any) -> None:
    """Safely display the explanation with sanitized HTML."""
    column.markdown(sanitize_html(explanation), unsafe_allow_html=True)

def display_references(references: List[Any], column: Any) -> None:
    """Safely display references with sanitized content."""
    if references:
        column.markdown("### References")
        for ref in references:
            title = getattr(ref, "title", None) or (ref.get("title") if isinstance(ref, dict) else "")
            url = getattr(ref, "url", None) or (ref.get("url") if isinstance(ref, dict) else "")
            title_esc = html.escape(title or "")
            url_esc = html.escape(str(url or ""))
            safe_html = f'<a href="{url_esc}" target="_blank" rel="noopener noreferrer">{title_esc or url_esc}</a>'
            column.markdown(safe_html, unsafe_allow_html=True)

def format_response(result: AnalysisResult, search_time: float, analysis_time: float) -> str:
    """Format an AnalysisResult into a user-facing markdown string.

    This accepts a validated AnalysisResult and produces the same layout as the
    previous legacy formatter for backward compatibility with the UI.
    """
    verdict = result.verdict.value if hasattr(result, "verdict") else str(result.get("verdict", "UNVERIFIABLE"))
    explanation = result.explanation if getattr(result, "explanation", None) else ""
    context = result.context or ""
    references = result.references or []

    # Build references markdown
    if references:
        refs_md = "\n".join([f"{i+1}. [{html.escape(r.title)}]({html.escape(str(r.url))})" for i, r in enumerate(references)])
    else:
        refs_md = "No references provided."

    total_time = search_time + analysis_time

    return f"""
⏱️ _Search completed in {search_time:.2f}s, Analysis in {analysis_time:.2f}s (Total: {total_time:.2f}s)_

{html.escape(verdict)}

### Explanation
{sanitize_html(explanation)}

### Additional Context
{sanitize_html(context)}

### References
{refs_md}
    """

async def analyze_statement(statement: str, raw_search_results: str, search_time: float) -> AnalysisResult:
    """Analyze a statement using the search results and return a validated AnalysisResult.

    We ask the LLM to return a single JSON object and validate it using parse_llm_json.
    """
    analysis_start = time.time()

    system_prompt = llm_system_prompt()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Statement: {statement}\n\nEvidence:\n{raw_search_results}"},
    ]

    # Use a single non-streamed request to simplify robust parsing
    completion = await client.chat.completions.create(
        model=llm,
        messages=messages,
    )

    full_response = completion.choices[0].message.content
    analysis_time = time.time() - analysis_start

    # Parse and validate into AnalysisResult
    ar = parse_llm_json(full_response)
    # Populate timings
    try:
        ar.search_time = float(search_time)
    except Exception:
        ar.search_time = search_time or 0.0
    try:
        ar.analysis_time = float(analysis_time)
    except Exception:
        ar.analysis_time = analysis_time or 0.0

    return ar

async def main():
    """Main function to create and run the Streamlit UI."""
    # Initialize session state variables
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "query_history" not in st.session_state:
        st.session_state.query_history = []
    if "current_query_id" not in st.session_state:
        st.session_state.current_query_id = None

    st.title("🔍 AI-Powered Fact Checker")
    st.markdown("""
    This tool helps verify statements by searching the web and analyzing the results using AI.
    Enter a statement or claim below to check its accuracy.
    """)
    
    if not st.session_state.query_history:
        st.info("ℹ️ Your query history will appear here after your first search. Use the > button at the top left to view and export your history.")
    else:
        st.info(f"ℹ️ You have {len(st.session_state.query_history)} saved queries. Use the > button at the top left to view and export your history.")

    with st.expander("ℹ️ Understanding the Truthfulness Ratings"):
        st.markdown("""
        Our fact-checker uses a 5-point rating system to evaluate statements:
        
        - **TRUE**: The statement is accurate and supported by reliable evidence
        - **MOSTLY TRUE**: The statement is largely accurate but needs minor clarification
        - **PARTIALLY TRUE**: The statement contains elements of both truth and inaccuracy
        - **MOSTLY FALSE**: The statement contains some truth but is largely inaccurate
        - **FALSE**: The statement is completely inaccurate or has no basis in fact
        
        _Note: Some claims may be marked as "UNVERIFIABLE" if there isn't enough reliable evidence to make a determination._
        """)

        
    # Sidebar for query history
    with st.sidebar:
        st.markdown("### Query History")
        st.warning("""
        Query history is stored in your browser session and will be lost if you refresh the page.
        Use the export button below to save your conversation history.
        """)
        
        if st.button("Clear History", key="clear_history"):
            st.session_state.messages = []
            st.session_state.query_history = []
            st.session_state.current_query_id = None
            st.caption("Clears local query history from your browser session.")
            st.markdown('<span class="sr-only">Clear history button. Press Enter to activate when focused.</span>', unsafe_allow_html=True)
            st.rerun()
        
        export_format = st.radio(
            "Export format:",
            ("JSON", "PDF"),
            horizontal=True
        )
            
        if st.button("Export History"):
            history = {
                "exported_at": datetime.now().isoformat(),
                "queries": st.session_state.query_history
            }
            if export_format == "JSON":
                st.download_button(
                    label="Download History (JSON)",
                    data=json.dumps(history, indent=2),
                    file_name=f"fact_check_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            elif export_format == "PDF":
                pdf_filename = f"fact_check_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                generate_pdf(st.session_state.query_history, pdf_filename)
                
                with open(pdf_filename, "rb") as pdf_file:
                    pdf_bytes = pdf_file.read()
                    pdf_base64 = base64.b64encode(pdf_bytes).decode()
                
                st.markdown(
                    f'<a href="data:application/pdf;base64,{pdf_base64}" download="{pdf_filename}">Download History (PDF)</a>',
                    unsafe_allow_html=True,
                )
        # Display query history with navigation
        for query in reversed(st.session_state.query_history):
            if st.button(f"{query['timestamp']} - {query['query'][:50]}..."):
                st.session_state.current_query_id = query['id']
                st.rerun()

    # Display chat messages from history with timestamp
    if st.session_state.current_query_id:
        # Show specific query from history
        query = next((q for q in st.session_state.query_history if q['id'] == st.session_state.current_query_id), None)
        if query:
            with st.chat_message("human"):
                st.markdown(f"**You**: {query['query']}", unsafe_allow_html=True)
            with st.chat_message("assistant"):
                st.markdown(query['response'], unsafe_allow_html=True)
                st.markdown("---")
                st.caption("ℹ️ Each fact-check is independent and based on current web evidence")
    else:
        # Show full conversation
        for message in st.session_state.messages:
            with st.chat_message("human" if isinstance(message, UserPrompt) else "assistant"):
                if isinstance(message, UserPrompt):
                    st.markdown(f"**You**: {message.content}", unsafe_allow_html=True)
                else:
                    st.markdown(f"**AI**: {message.content}", unsafe_allow_html=True)
                    st.markdown("---")
                    st.caption("ℹ️ Each fact-check is independent and based on current web evidence")

    # Handle user input
    if prompt := st.chat_input("Enter a statement to fact-check..."):
        # Display user message
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append(UserPrompt(content=prompt))

        # Display AI response with progress
        response_content = ""
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            # First, search the web (using BraveSearchClient abstraction)
            search_start = time.time()
            with st.spinner("🔍 Searching the web..."):
                brave_api_key = os.getenv("BRAVE_API_KEY", None)
                http_client = get_async_client()
                try:
                    bclient = BraveSearchClient(api_key=brave_api_key, client=http_client)
                    results = await bclient.search(f"fact check {prompt}", count=5)
                    # Convert typed results into the legacy raw string format expected by the analyzer
                    raw_search_results = "\n---\n".join(
                        [f"[Source: {r.title}]\nURL: {r.url}\n{r.description}\n" for r in results]
                    )
                except Exception as e:
                    raw_search_results = "[Error] Could not perform web search."
                    st.error("Error performing web search. See logs for details.")
            search_time = time.time() - search_start

            # Then analyze the results
            with st.spinner("🤔 Analyzing evidence..."):
                analysis_result = await analyze_statement(prompt, raw_search_results, search_time)
                response_content = format_response(analysis_result, search_time, analysis_result.analysis_time)
                # Record basic telemetry in session state (in-memory only)
                try:
                    if "metrics" not in st.session_state:
                        st.session_state.metrics = []
                    st.session_state.metrics.append({
                        "timestamp": datetime.now().isoformat(),
                        "search_time": float(search_time),
                        "analysis_time": float(analysis_result.analysis_time),
                        "total_time": float(search_time) + float(analysis_result.analysis_time),
                    })
                except Exception:
                    # telemetry is best-effort; do not block the UI
                    pass
                message_placeholder.markdown(response_content, unsafe_allow_html=True)
        
        # Store the query in history
        query_id = str(time.time())
        st.session_state.query_history.append({
            'id': query_id,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'query': prompt,
            'response': response_content
        })
        
        # Add to messages and set as current query
        st.session_state.messages.append(ModelTextResponse(content=response_content))
        st.session_state.current_query_id = query_id
        
        # Force refresh to update query history sidebar
        st.rerun()

if __name__ == "__main__":
    asyncio.run(main())

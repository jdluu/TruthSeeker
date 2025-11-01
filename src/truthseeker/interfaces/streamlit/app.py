"""Main Streamlit application entry point."""

import asyncio
import base64
import json
import time
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st
from pydantic_ai.messages import ModelTextResponse, UserPrompt

from ...application.fact_checker import FactCheckerService
from ...config.settings import get_settings
from ...domain.models import AnalysisResult
from ...infrastructure.http.client import get_async_client
from ...infrastructure.llm.client import LLMClient
from ...infrastructure.llm.parser import LLMResponseParser
from ...infrastructure.search.brave_client import BraveSearchClient
from ...utils.pdf import generate_pdf
from .components import display_explanation, display_references, display_verdict
from .formatters import format_analysis_result


def _initialize_session_state() -> None:
    """Initialize Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "query_history" not in st.session_state:
        st.session_state.query_history = []
    if "current_query_id" not in st.session_state:
        st.session_state.current_query_id = None
    if "metrics" not in st.session_state:
        st.session_state.metrics = []


def _create_fact_checker_service() -> FactCheckerService:
    """Create and configure fact-checker service with dependency injection."""
    settings = get_settings()
    http_client = get_async_client(settings.http_timeout_seconds)

    search_client = BraveSearchClient(
        api_key=settings.brave_api_key,
        http_client=http_client,
        cache_ttl=settings.search_cache_ttl,
    )

    llm_client = LLMClient(
        api_key=settings.deepseek_api_key,
        model=settings.llm_model,
    )

    response_parser = LLMResponseParser()

    return FactCheckerService(
        search_client=search_client,
        llm_client=llm_client,
        response_parser=response_parser,
    )


@st.cache_resource
def _get_fact_checker_service() -> FactCheckerService:
    """Get cached fact-checker service instance."""
    return _create_fact_checker_service()


def _render_header() -> None:
    """Render application header."""
    st.title("🔍 AI-Powered Fact Checker")
    st.markdown(
        "This tool helps verify statements by searching the web and analyzing the results using AI. "
        "Enter a statement or claim below to check its accuracy."
    )


def _render_info_section() -> None:
    """Render information section with verdict explanations."""
    history_count = len(st.session_state.query_history)
    if history_count == 0:
        st.info(
            "ℹ️ Your query history will appear here after your first search. "
            "Use the > button at the top left to view and export your history."
        )
    else:
        st.info(
            f"ℹ️ You have {history_count} saved queries. "
            "Use the > button at the top left to view and export your history."
        )

    with st.expander("ℹ️ Understanding the Truthfulness Ratings"):
        st.markdown(
            """
            Our fact-checker uses a 5-point rating system to evaluate statements:
            
            - **TRUE**: The statement is accurate and supported by reliable evidence
            - **MOSTLY TRUE**: The statement is largely accurate but needs minor clarification
            - **PARTIALLY TRUE**: The statement contains elements of both truth and inaccuracy
            - **MOSTLY FALSE**: The statement contains some truth but is largely inaccurate
            - **FALSE**: The statement is completely inaccurate or has no basis in fact
            
            _Note: Some claims may be marked as "UNVERIFIABLE" if there isn't enough reliable evidence to make a determination._
            """
        )


def _render_sidebar() -> None:
    """Render sidebar with query history and export options."""
    with st.sidebar:
        st.markdown("### Query History")
        st.warning(
            "Query history is stored in your browser session and will be lost if you refresh the page. "
            "Use the export button below to save your conversation history."
        )

        if st.button("Clear History", key="clear_history"):
            st.session_state.messages = []
            st.session_state.query_history = []
            st.session_state.current_query_id = None
            st.caption("Clears local query history from your browser session.")
            st.markdown(
                '<span class="sr-only">Clear history button. Press Enter to activate when focused.</span>',
                unsafe_allow_html=True,
            )
            st.rerun()

        export_format = st.radio(
            "Export format:",
            ("JSON", "PDF"),
            horizontal=True,
        )

        if st.button("Export History"):
            history: Dict[str, Any] = {
                "exported_at": datetime.now().isoformat(),
                "queries": st.session_state.query_history,
            }
            if export_format == "JSON":
                st.download_button(
                    label="Download History (JSON)",
                    data=json.dumps(history, indent=2),
                    file_name=f"fact_check_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                )
            elif export_format == "PDF":
                pdf_filename = (
                    f"fact_check_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                )
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
                st.session_state.current_query_id = query["id"]
                st.rerun()


def _render_chat_history() -> None:
    """Render chat message history."""
    if st.session_state.current_query_id:
        # Show specific query from history
        query = next(
            (
                q
                for q in st.session_state.query_history
                if q["id"] == st.session_state.current_query_id
            ),
            None,
        )
        if query:
            with st.chat_message("human"):
                st.markdown(f"**You**: {query['query']}", unsafe_allow_html=True)
            with st.chat_message("assistant"):
                st.markdown(query["response"], unsafe_allow_html=True)
                st.markdown("---")
                st.caption(
                    "ℹ️ Each fact-check is independent and based on current web evidence"
                )
    else:
        # Show full conversation
        for message in st.session_state.messages:
            with st.chat_message(
                "human" if isinstance(message, UserPrompt) else "assistant"
            ):
                if isinstance(message, UserPrompt):
                    st.markdown(f"**You**: {message.content}", unsafe_allow_html=True)
                else:
                    st.markdown(f"**AI**: {message.content}", unsafe_allow_html=True)
                    st.markdown("---")
                    st.caption(
                        "ℹ️ Each fact-check is independent and based on current web evidence"
                    )


def _record_metrics(search_time: float, analysis_time: float) -> None:
    """Record performance metrics (best-effort)."""
    try:
        st.session_state.metrics.append(
            {
                "timestamp": datetime.now().isoformat(),
                "search_time": float(search_time),
                "analysis_time": float(analysis_time),
                "total_time": float(search_time) + float(analysis_time),
            }
        )
    except Exception:
        pass  # Telemetry is best-effort; do not block the UI


async def _handle_user_input(prompt: str, service: FactCheckerService) -> None:
    """Handle user input and perform fact-checking."""
    # Display user message
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append(UserPrompt(content=prompt))

    # Display AI response with progress
    with st.chat_message("assistant"):
        message_placeholder = st.empty()

        # Perform fact-checking
        with st.spinner("🔍 Searching the web..."):
            try:
                analysis_result = await service.fact_check(prompt)
            except Exception as e:
                st.error(f"Error performing fact-check: {str(e)}")
                from ...domain.models import Verdict

                analysis_result = AnalysisResult(
                    verdict=Verdict.UNVERIFIABLE,
                    explanation=f"An error occurred: {str(e)}",
                    context=None,
                    references=[],
                    search_time=0.0,
                    analysis_time=0.0,
                )

        # Format and display results
        response_content = format_analysis_result(
            analysis_result,
            analysis_result.search_time,
            analysis_result.analysis_time,
        )
        message_placeholder.markdown(response_content, unsafe_allow_html=True)

        # Record metrics
        _record_metrics(
            analysis_result.search_time,
            analysis_result.analysis_time,
        )

    # Store in history
    query_id = str(time.time())
    st.session_state.query_history.append(
        {
            "id": query_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "query": prompt,
            "response": response_content,
        }
    )

    # Add to messages and set as current query
    st.session_state.messages.append(ModelTextResponse(content=response_content))
    st.session_state.current_query_id = query_id

    # Force refresh
    st.rerun()


def _get_custom_css() -> str:
    """Get custom CSS for the application."""
    return """
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
"""


def create_app() -> None:
    """Create and run the Streamlit application."""
    # Page configuration
    st.set_page_config(
        page_title="AI Fact Checker",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Custom CSS
    st.markdown(_get_custom_css(), unsafe_allow_html=True)

    # Initialize session state
    _initialize_session_state()

    # Get service
    service = _get_fact_checker_service()

    # Render UI components
    _render_header()
    _render_info_section()
    _render_sidebar()
    _render_chat_history()

    # Handle user input
    if prompt := st.chat_input("Enter a statement to fact-check..."):
        asyncio.run(_handle_user_input(prompt, service))


# Main entry point
if __name__ == "__main__":
    create_app()


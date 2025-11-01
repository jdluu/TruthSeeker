"""Main Streamlit application entry point."""

import asyncio
import base64
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

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
        # Header with icon
        st.markdown(
            """
            <div style='padding: 0.5rem 0 1rem 0; border-bottom: 2px solid #404040; margin-bottom: 1rem;'>
                <h2 style='margin: 0; color: #FFFFFF; font-size: 1.5rem; font-weight: 600;'>📜 Query History</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Info banner
        history_count = len(st.session_state.query_history)
        if history_count > 0:
            st.info(
                f"💾 You have **{history_count}** saved query{'ies' if history_count != 1 else ''}. "
                "Export your history to save it permanently.",
                icon="ℹ️",
            )
        else:
            st.info(
                "💾 Your query history will appear here. Export to save permanently.",
                icon="ℹ️",
            )

        # Action buttons section
        st.markdown("### Actions")
        
        if st.button("🗑️ Clear", key="clear_history", use_container_width=True):
            st.session_state.messages = []
            st.session_state.query_history = []
            st.session_state.current_query_id = None
            st.rerun()

        # Export format selector (non-searchable dropdown)
        export_format = st.selectbox(
            "Export Format",
            options=["JSON", "PDF", "TXT"],
            index=0,
            key="export_format_select",
            help="Select the format for exporting your query history",
        )
        
        # Inject JavaScript to prevent typing in the selectbox input
        st.markdown(
            """
            <script>
                (function() {
                    function disableTyping() {
                        const selectInput = document.querySelector('[data-baseweb="select"] input[aria-label="Export Format"]');
                        if (selectInput && !selectInput.hasAttribute('data-typing-disabled')) {
                            // Mark as processed
                            selectInput.setAttribute('data-typing-disabled', 'true');
                            
                            // Prevent typing but allow clicking
                            selectInput.addEventListener('keydown', function(e) {
                                // Allow Escape, Enter, Tab, Arrow keys for navigation
                                if (!['Escape', 'Enter', 'Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
                                    e.preventDefault();
                                    return false;
                                }
                            }, true);
                            selectInput.addEventListener('keypress', function(e) {
                                e.preventDefault();
                                return false;
                            }, true);
                            selectInput.addEventListener('input', function(e) {
                                // Prevent text input but allow dropdown to work
                                if (e.inputType && e.inputType.startsWith('insert')) {
                                    e.preventDefault();
                                    return false;
                                }
                            }, true);
                            // Hide caret
                            selectInput.style.caretColor = 'transparent';
                            selectInput.style.cursor = 'pointer';
                        }
                    }
                    
                    // Run immediately
                    disableTyping();
                    
                    // Also run after a short delay for dynamic rendering
                    setTimeout(disableTyping, 100);
                    
                    // Watch for DOM changes in sidebar only (more efficient)
                    const sidebar = document.querySelector('[data-testid="stSidebar"]');
                    if (sidebar) {
                        const observer = new MutationObserver(function(mutations) {
                            let shouldCheck = false;
                            for (let mutation of mutations) {
                                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                                    shouldCheck = true;
                                    break;
                                }
                            }
                            if (shouldCheck) {
                                disableTyping();
                            }
                        });
                        observer.observe(sidebar, {
                            childList: true,
                            subtree: true
                        });
                    }
                })();
            </script>
            """,
            unsafe_allow_html=True,
        )

        if st.button("📥 Export History", key="export_history", use_container_width=True):
            if history_count == 0:
                st.warning("No history to export.")
            else:
                history: Dict[str, Any] = {
                    "exported_at": datetime.now().isoformat(),
                    "queries": st.session_state.query_history,
                }
                
                if export_format == "JSON":
                    st.download_button(
                        label=f"⬇️ Download JSON ({history_count} queries)",
                        data=json.dumps(history, indent=2),
                        file_name=f"fact_check_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True,
                    )
                elif export_format == "PDF":
                    pdf_filename = (
                        f"fact_check_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    )
                    try:
                        generate_pdf(st.session_state.query_history, pdf_filename)

                        with open(pdf_filename, "rb") as pdf_file:
                            pdf_bytes = pdf_file.read()
                            pdf_base64 = base64.b64encode(pdf_bytes).decode()

                        st.markdown(
                            f'<a href="data:application/pdf;base64,{pdf_base64}" download="{pdf_filename}" style="display: block; padding: 0.75rem; text-align: center; background-color: #FF4B4B; color: white; border-radius: 0.5rem; text-decoration: none; margin-top: 0.5rem; font-weight: 500; transition: all 0.2s;">⬇️ Download PDF ({history_count} queries)</a>',
                            unsafe_allow_html=True,
                        )
                    finally:
                        # Clean up temporary PDF file
                        try:
                            pdf_path = Path(pdf_filename)
                            if pdf_path.exists():
                                pdf_path.unlink()
                        except Exception:
                            pass  # Best effort cleanup
                elif export_format == "TXT":
                    # Generate plain text format
                    txt_content = "=" * 70 + "\n"
                    txt_content += "AI FACT CHECKER - QUERY HISTORY\n"
                    txt_content += "=" * 70 + "\n\n"
                    txt_content += f"Exported at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    txt_content += f"Total Queries: {history_count}\n"
                    txt_content += "=" * 70 + "\n\n"
                    
                    for idx, query in enumerate(st.session_state.query_history, 1):
                        txt_content += f"\n{'=' * 70}\n"
                        txt_content += f"QUERY #{idx}\n"
                        txt_content += f"{'=' * 70}\n"
                        txt_content += f"Timestamp: {query['timestamp']}\n"
                        txt_content += f"\nQuestion: {query['query']}\n"
                        txt_content += "\n" + "-" * 70 + "\n"
                        txt_content += "Response:\n"
                        txt_content += "-" * 70 + "\n"
                        # Strip HTML tags from response for plain text
                        clean_response = re.sub(r'<[^>]+>', '', query['response'])
                        txt_content += clean_response + "\n"
                        txt_content += "\n"
                    
                    st.download_button(
                        label=f"⬇️ Download TXT ({history_count} queries)",
                        data=txt_content,
                        file_name=f"fact_check_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

        # Query history section
        if history_count > 0:
            st.markdown("---")
            st.markdown("### Recent Queries")

            # Display query history with improved styling
            for idx, query in enumerate(reversed(st.session_state.query_history)):
                is_active = (
                    st.session_state.current_query_id == query["id"]
                )
                
                # Create a styled container for each query (dark theme)
                border_color = "#FF4B4B" if is_active else "#404040"
                query_preview = query['query'][:60] + "..." if len(query['query']) > 60 else query['query']
                
                # Create styled card container with dark theme
                active_badge = ""
                if is_active:
                    active_badge = '<span style="background-color: #FF4B4B; color: white; padding: 0.125rem 0.5rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; margin-left: auto;">ACTIVE</span>'
                
                # Dark theme colors
                card_bg = "#2E2E2E" if not is_active else "#3A2E2E"
                
                query_card_html = f"""
                <div class="query-history-card" style='
                    border: 2px solid {border_color};
                    border-radius: 8px;
                    padding: 0.75rem;
                    margin-bottom: 0.75rem;
                    background-color: {card_bg};
                    transition: all 0.2s ease;
                    cursor: pointer;
                '>
                    <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;'>
                        <span style='font-size: 0.875rem; color: #CCCCCC;'>🕒</span>
                        <span style='font-size: 0.875rem; color: #CCCCCC; font-weight: 500;'>{query['timestamp']}</span>
                        {active_badge}
                    </div>
                    <div style='
                        color: #FFFFFF;
                        font-weight: 500;
                        line-height: 1.4;
                        word-wrap: break-word;
                        font-size: 0.9rem;
                    '>{query_preview}</div>
                </div>
                """
                
                st.markdown(query_card_html, unsafe_allow_html=True)
                
                # Button to view query details
                if st.button(
                    "📖 View Details" if not is_active else "✓ Currently Viewing",
                    key=f"query_btn_{query['id']}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state.current_query_id = query["id"]
                    st.rerun()
                
                st.markdown("<br>", unsafe_allow_html=True)  # Add spacing between cards


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
            if isinstance(message, dict):
                role = message.get("role", "assistant")
                content = message.get("content", "")
                with st.chat_message(role):
                    if role == "user":
                        st.markdown(f"**You**: {content}", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**AI**: {content}", unsafe_allow_html=True)
                        st.markdown("---")
                        st.markdown(
                            '<p style="color: #CCCCCC; font-size: 0.875rem; margin-top: 1rem; padding: 0.75rem; background-color: #2E2E2E; border-radius: 0.5rem; border-left: 3px solid #FF4B4B;"><strong>ℹ️ Note:</strong> Each fact-check is independent and based on current web evidence. Results may vary if checked again due to changing web content.</p>',
                            unsafe_allow_html=True,
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
    """Handle user input and perform fact-checking with streaming support."""
    # Display user message
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display AI response with streaming
    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        message_placeholder = st.empty()

        def stream_callback(status: str) -> None:
            """Callback for streaming status updates."""
            status_messages = {
                "Analyzing...": "🤖 Analyzing statement...",
                "Searching for evidence...": "🔍 Searching the web for evidence...",
            }
            display_text = status_messages.get(status, f"⏳ {status}")
            status_placeholder.info(display_text)

        # Perform fact-checking with streaming
        try:
            # Use streaming for better UX
            analysis_result = await service.fact_check(
                prompt, stream_callback=stream_callback
            )
        except Exception as e:
            status_placeholder.empty()
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

        # Clear status and display final results
        status_placeholder.empty()
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
    st.session_state.messages.append({"role": "assistant", "content": response_content})
    st.session_state.current_query_id = query_id

    # Force refresh
    st.rerun()


def _get_custom_css() -> str:
    """Get custom CSS for the application with unified dark theme."""
    return """
<style>
    /* Unified Dark Theme - Main Content */
    .main .block-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 1rem;
        background-color: #1A1C20;
        color: #FFFFFF;
    }
    
    /* Main app background */
    .stApp {
        background-color: #1A1C20;
    }
    
    /* All text should be white/light on dark background */
    .main p, .main h1, .main h2, .main h3, .main h4, .main h5, .main h6,
    .main div, .main span, .main li, .main td, .main th {
        color: #FFFFFF !important;
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
        color: #FF6B6B !important;
        text-decoration: none;
    }
    a:hover {
        color: #FF4B4B !important;
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
    
    /* Query history cards */
    .query-history-card {
        transition: all 0.2s ease;
    }
    .query-history-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(255, 75, 75, 0.3);
        border-color: #FF4B4B !important;
    }
    
    /* Unified Dark Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1A1C20 !important;
        border-right: 1px solid #2E2E2E;
    }
    
    [data-testid="stSidebar"] .element-container {
        padding: 0.25rem 0;
    }
    
    /* Sidebar text colors */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: #FFFFFF !important;
    }
    
    /* Info boxes in sidebar - dark theme */
    [data-testid="stSidebar"] [data-baseweb="notification"] {
        background-color: #2E2E2E !important;
        color: #FFFFFF !important;
        border: 1px solid #404040 !important;
    }
    
    /* Sidebar buttons - unified styling */
    [data-testid="stSidebar"] .stButton > button {
        background-color: #2E2E2E !important;
        color: #FFFFFF !important;
        border: 1px solid #404040 !important;
        transition: all 0.2s ease;
        border-radius: 0.5rem;
        font-weight: 500;
    }
    
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #404040 !important;
        border-color: #FF4B4B !important;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(255, 75, 75, 0.2);
    }
    
    /* Primary buttons in sidebar */
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background-color: #FF4B4B !important;
        color: #FFFFFF !important;
        border: 1px solid #FF4B4B !important;
    }
    
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background-color: #FF6B6B !important;
        border-color: #FF6B6B !important;
    }
    
    /* Selectbox in sidebar - non-searchable dropdown styling */
    [data-testid="stSidebar"] [data-baseweb="select"],
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background-color: #2E2E2E !important;
        color: #FFFFFF !important;
        border: 1px solid #404040 !important;
    }
    
    [data-testid="stSidebar"] [data-baseweb="select"] input {
        color: #FFFFFF !important;
        background-color: #2E2E2E !important;
        caret-color: transparent !important;
        cursor: pointer !important;
    }
    
    [data-testid="stSidebar"] [data-baseweb="select"] input:focus {
        caret-color: transparent !important;
    }
    
    [data-testid="stSidebar"] [data-baseweb="select"] input::placeholder {
        color: #888888 !important;
    }
    
    
    /* Dropdown menu items */
    [data-baseweb="popover"] [role="option"] {
        background-color: #2E2E2E !important;
        color: #FFFFFF !important;
    }
    
    [data-baseweb="popover"] [role="option"]:hover {
        background-color: #404040 !important;
    }
    
    /* Button styling improvements */
    .stButton > button {
        transition: all 0.2s ease;
        border-radius: 0.5rem;
        font-weight: 500;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }
    
    /* Info boxes - dark theme */
    [data-baseweb="notification"] {
        background-color: #2E2E2E !important;
        color: #FFFFFF !important;
        border: 1px solid #404040 !important;
    }
    
    /* Captions and small text - ensure readability */
    .stCaption {
        color: #CCCCCC !important;
        font-size: 0.875rem !important;
    }
    
    /* Input fields - dark theme */
    [data-baseweb="input"] {
        background-color: #2E2E2E !important;
        color: #FFFFFF !important;
        border: 1px solid #404040 !important;
    }
    
    [data-baseweb="input"] input {
        color: #FFFFFF !important;
    }
    
    [data-baseweb="input"] input::placeholder {
        color: #888888 !important;
        opacity: 1;
    }
    
    /* Expanders - dark theme */
    [data-baseweb="accordion"] {
        background-color: #2E2E2E !important;
        border: 1px solid #404040 !important;
    }
    
    /* Download buttons */
    [data-testid="stDownloadButton"] > button {
        background-color: #FF4B4B !important;
        color: #FFFFFF !important;
        border: 1px solid #FF4B4B !important;
    }
    
    [data-testid="stDownloadButton"] > button:hover {
        background-color: #FF6B6B !important;
    }
    
    /* Ensure all markdown text is readable */
    .main .stMarkdown {
        color: #FFFFFF !important;
    }
    
    .main .stMarkdown p {
        color: #FFFFFF !important;
    }
    
    .main .stMarkdown strong {
        color: #FFFFFF !important;
    }
    
    /* Expander text */
    [data-baseweb="accordion"] [data-baseweb="typography"] {
        color: #FFFFFF !important;
    }
    
    /* Divider lines */
    hr {
        border-color: #404040 !important;
        margin: 1rem 0 !important;
    }
    
    /* Section headers */
    h3 {
        color: #FFFFFF !important;
    }
    
    /* Ensure expander content is readable */
    [data-baseweb="accordion"] .streamlit-expanderContent {
        color: #FFFFFF !important;
    }
    
    [data-baseweb="accordion"] .streamlit-expanderContent p,
    [data-baseweb="accordion"] .streamlit-expanderContent li {
        color: #CCCCCC !important;
    }
    
    /* Top header bar - unified dark theme */
    header[data-testid="stHeader"] {
        background-color: #1A1C20 !important;
        border-bottom: 1px solid #2E2E2E !important;
    }
    
    /* Hide the gradient line if it exists */
    .stApp > header::before,
    .stApp > header::after {
        display: none !important;
    }
    
    /* Main app wrapper */
    .stApp > div:first-child {
        background-color: #1A1C20 !important;
    }
    
    /* Bottom footer/decoration area */
    footer[data-testid="stFooter"],
    .stApp footer,
    footer {
        background-color: #1A1C20 !important;
        border-top: 1px solid #2E2E2E !important;
        color: #CCCCCC !important;
    }
    
    footer[data-testid="stFooter"] *,
    footer * {
        color: #CCCCCC !important;
    }
    
    /* Footer text and links */
    footer a,
    footer p,
    footer div,
    footer span {
        color: #888888 !important;
    }
    
    /* Chat input container - unified background */
    [data-testid="stChatInputContainer"] {
        border-top: 1px solid #2E2E2E !important;
        padding: 1rem !important;
        background-color: #1A1C20 !important;
    }
    
    /* Chat input textarea styling - distinct darker background */
    [data-testid="stChatInputTextInput"] textarea {
        background-color: #2E2E2E !important;
        color: #FFFFFF !important;
        border: 1px solid #404040 !important;
        border-radius: 0.5rem !important;
    }
    
    [data-testid="stChatInputTextInput"] textarea:focus {
        border-color: #FF4B4B !important;
        box-shadow: 0 0 0 2px rgba(255, 75, 75, 0.2) !important;
        background-color: #2E2E2E !important;
    }
    
    [data-testid="stChatInputTextInput"] textarea::placeholder {
        color: #888888 !important;
        opacity: 1 !important;
    }
    
    /* Chat input send button */
    [data-testid="stChatInputContainer"] button[aria-label*="Send"],
    [data-testid="stChatInputContainer"] button[type="submit"] {
        background-color: #FF4B4B !important;
        color: #FFFFFF !important;
        border: 1px solid #FF4B4B !important;
    }
    
    [data-testid="stChatInputContainer"] button[aria-label*="Send"]:hover,
    [data-testid="stChatInputContainer"] button[type="submit"]:hover {
        background-color: #FF6B6B !important;
        border-color: #FF6B6B !important;
    }
    
    
    /* Remove any gradient decorations */
    .stApp::before,
    .stApp::after {
        display: none !important;
    }
    
    /* Ensure all sections match dark theme */
    section[data-testid="stSidebar"] {
        background-color: #1A1C20 !important;
    }
    
    /* Main content area background */
    .main .block-container {
        background-color: transparent !important;
    }
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

    # Custom CSS with unified dark theme
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


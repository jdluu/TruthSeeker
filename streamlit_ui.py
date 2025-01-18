from dotenv import load_dotenv
from httpx import AsyncClient
from datetime import datetime
import streamlit as st
import asyncio
import os
import logfire
import re
import time
import bleach
import html

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.messages import ModelTextResponse, UserPrompt, SystemPrompt

from web_search_agent import search_web_direct

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
def init_clients():
    load_dotenv()
    llm = os.getenv('LLM_MODEL', 'hf:mistralai/Mistral-7B-Instruct-v0.3')
    client = AsyncOpenAI(
        base_url='https://glhf.chat/api/openai/v1',
        api_key=os.getenv('GLHF_API_KEY')
    )
    logfire.configure(send_to_logfire='if-token-present')
    logfire.instrument_openai(client)
    return client, llm

client, llm = init_clients()
model = OpenAIModel(llm, openai_client=client)

def sanitize_html(content: str) -> str:
    """Sanitize HTML content to prevent XSS attacks."""
    allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li', 'span', 'div']
    allowed_attributes = {
        'a': ['href', 'title'],
        'span': ['class'],
        'div': ['class']
    }
    return bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True
    )

def display_verdict(verdict: str, column):
    """Safely display the verdict with proper styling."""
    verdict = html.escape(verdict.upper())
    safe_html = f'<div class="verdict {verdict.lower()}">{verdict}</div>'
    column.markdown(safe_html, unsafe_allow_html=True)

def display_explanation(explanation: str, column):
    """Safely display the explanation with sanitized HTML."""
    column.markdown(sanitize_html(explanation), unsafe_allow_html=True)

def display_references(references: list, column):
    """Safely display references with sanitized content."""
    if references:
        column.markdown("### References")
        for ref in references:
            title = html.escape(ref.get('title', ''))
            url = html.escape(ref.get('url', ''))
            safe_html = f'<a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>'
            column.markdown(safe_html, unsafe_allow_html=True)

def format_response(response_text, search_time, analysis_time):
    """Format the response text into a structured output with responsive design."""
    verdict_match = re.search(r'<verdict>(.*?)</verdict>', response_text, re.DOTALL)
    explanation_match = re.search(r'<explanation>(.*?)</explanation>', response_text, re.DOTALL)
    context_match = re.search(r'<context>(.*?)</context>', response_text, re.DOTALL)
    references_match = re.search(r'<references>(.*?)</references>', response_text, re.DOTALL)
    
    verdict = verdict_match.group(1).strip() if verdict_match else ""
    explanation = explanation_match.group(1).strip() if explanation_match else ""
    context = context_match.group(1).strip() if context_match else ""
    references = references_match.group(1).strip() if references_match else ""
    
    total_time = search_time + analysis_time
    
    return f"""
⏱️ _Search completed in {search_time:.2f}s, Analysis in {analysis_time:.2f}s (Total: {total_time:.2f}s)_

{verdict}

### Explanation
{explanation}

### Additional Context
{context}

### References
{references}
    """

async def analyze_statement(statement, raw_search_results, search_time):
    """Analyze a statement using the search results."""
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
        messages=messages,
        stream=True
    )

    full_response = ""
    async for chunk in completion:
        if chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            full_response += content
            analysis_time = time.time() - analysis_start
            yield format_response(full_response, search_time, analysis_time)

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

    # Initialize session state variables
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "query_history" not in st.session_state:
        st.session_state.query_history = []
    if "current_query_id" not in st.session_state:
        st.session_state.current_query_id = None
        
    # Sidebar for query history
    with st.sidebar:
        st.markdown("### Query History")
        st.warning("""
        Query history is stored in your browser session and will be lost if you refresh the page.
        Use the export button below to save your conversation history.
        """)
        
        if st.button("Clear History"):
            st.session_state.messages = []
            st.session_state.query_history = []
            st.session_state.current_query_id = None
            st.rerun()
            
        if st.button("Export History"):
            import json
            from datetime import datetime
            history = {
                "exported_at": datetime.now().isoformat(),
                "queries": st.session_state.query_history
            }
            st.download_button(
                label="Download History",
                data=json.dumps(history, indent=2),
                file_name=f"fact_check_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
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
            
            # First, search the web
            search_start = time.time()
            with st.spinner("🔍 Searching the web..."):
                async with AsyncClient() as http_client:
                    brave_api_key = os.getenv('BRAVE_API_KEY', None)
                    raw_search_results = await search_web_direct(http_client, brave_api_key, f"fact check {prompt}")
            search_time = time.time() - search_start

            # Then analyze the results
            with st.spinner("🤔 Analyzing evidence..."):
                async for formatted_chunk in analyze_statement(prompt, raw_search_results, search_time):
                    response_content = formatted_chunk
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

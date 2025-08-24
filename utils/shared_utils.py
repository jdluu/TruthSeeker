from typing import List, Dict, Tuple
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
import colorama
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def format_output(verdict: str, explanation: str, context: str, references: List[Dict]) -> Tuple:
    """Format the output for both terminal and Streamlit display"""
    # Create verdict panel
    verdict_text = Text(verdict, style="bold green")
    verdict_panel = Panel(verdict_text, title="Verdict", border_style="green")
    
    # Create explanation panel
    explanation_panel = Panel(explanation, title="Explanation", border_style="blue")
    
    # Create context panel if provided
    context_panel = Panel(context, title="Context & Nuance", border_style="magenta") if context else None
    
    # Create references table
    ref_table = Table(title="References", show_header=True, header_style="bold cyan")
    ref_table.add_column("#", style="cyan", justify="right")
    ref_table.add_column("Source", style="magenta")
    ref_table.add_column("URL", style="blue")
    
    for i, ref in enumerate(references, 1):
        ref_table.add_row(str(i), ref['title'], ref['url'])
    
    return verdict_panel, explanation_panel, context_panel, ref_table

def parse_response(response: str) -> Tuple[str, str, str, List[Dict]]:
    """Parse the AI response into structured components.

    Preferred path: use the structured JSON LLM parser (Pydantic-validated).
    Falls back to the legacy regex/split-based parsing if the structured parser
    cannot be imported or fails.
    """
    try:
        # Local import to avoid hard dependency during incremental refactor
        from src.truthseeker.llm.parser import parse_llm_json  # type: ignore
        ar = parse_llm_json(response)
        ref_list = [{"title": r.title, "url": str(r.url)} for r in ar.references]
        return ar.verdict.value, ar.explanation, ar.context or "", ref_list
    except Exception:
        logger.warning("Structured LLM parser unavailable or failed; falling back to legacy parsing.")

    # Legacy fallback (kept for backward compatibility)
    try:
        verdict = response.split("<verdict>")[1].split("</verdict>")[0].strip()
        explanation = response.split("<explanation>")[1].split("</explanation>")[0].strip()
        context = response.split("<context>")[1].split("</context>")[0].strip()
        references = response.split("<references>")[1].split("</references>")[0].strip()
    except Exception:
        logger.exception("Failed to parse response using legacy parser; returning unverifiable placeholder.")
        return "UNVERIFIABLE", "Could not parse model output.", "", []

    # Convert references to list of dicts
    ref_list: List[Dict] = []
    for ref in references.split("\n"):
        if ref.strip():
            try:
                num, rest = ref.split(". ", 1)
                name, url = rest.split(" - ", 1)
                ref_list.append({"title": name, "url": url})
            except ValueError:
                logger.warning(f"Could not parse reference: {ref}")
                continue

    return verdict, explanation, context, ref_list

def init_logging():
    """Initialize logging and colorama"""
    colorama.init()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

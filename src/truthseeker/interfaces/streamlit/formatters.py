"""Formatting utilities for Streamlit display."""

import html

from ...domain.models import AnalysisResult
from ...utils.sanitization import sanitize_html


def format_analysis_result(
    result: AnalysisResult, search_time: float, analysis_time: float
) -> str:
    """Format AnalysisResult into markdown string for display.

    Args:
        result: AnalysisResult to format.
        search_time: Search time in seconds.
        analysis_time: Analysis time in seconds.

    Returns:
        Formatted markdown string.
    """
    verdict = result.verdict.value
    explanation = result.explanation
    context = result.context or ""
    references = result.references or []

    # Build references markdown
    if references:
        refs_md = "\n".join(
            [
                f"{i+1}. [{html.escape(r.title)}]({html.escape(str(r.url))})"
                for i, r in enumerate(references)
            ]
        )
    else:
        refs_md = "No references provided."

    total_time = search_time + analysis_time

    return f"""⏱️ _Search completed in {search_time:.2f}s, Analysis in {analysis_time:.2f}s (Total: {total_time:.2f}s)_

{html.escape(verdict)}

### Explanation
{sanitize_html(explanation)}

### Additional Context
{sanitize_html(context)}

### References
{refs_md}
"""


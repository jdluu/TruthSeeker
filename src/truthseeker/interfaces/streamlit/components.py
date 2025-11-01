"""Reusable Streamlit UI components."""

import html
from typing import Any, List

import streamlit as st

from ...domain.models import AnalysisResult, Reference
from ...utils.sanitization import sanitize_html


def display_verdict(verdict: Any, column: Any) -> None:
    """Display verdict with proper styling.

    Args:
        verdict: Verdict enum or string value.
        column: Streamlit column/container to display in.
    """
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
    """Display explanation with sanitized HTML.

    Args:
        explanation: Explanation text.
        column: Streamlit column/container to display in.
    """
    column.markdown(sanitize_html(explanation), unsafe_allow_html=True)


def display_references(references: List[Any], column: Any) -> None:
    """Display references with sanitized content.

    Args:
        references: List of Reference objects or dicts.
        column: Streamlit column/container to display in.
    """
    if not references:
        return

    column.markdown("### References")
    for ref in references:
        if isinstance(ref, Reference):
            title = ref.title
            url = str(ref.url)
        elif isinstance(ref, dict):
            title = ref.get("title", "")
            url = ref.get("url", "")
        else:
            title = getattr(ref, "title", "")
            url = getattr(ref, "url", "")

        title_esc = html.escape(title or "")
        url_esc = html.escape(str(url or ""))
        safe_html = (
            f'<a href="{url_esc}" target="_blank" rel="noopener noreferrer">'
            f"{title_esc or url_esc}</a>"
        )
        column.markdown(safe_html, unsafe_allow_html=True)


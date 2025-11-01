"""Input sanitization utilities for security."""

import re
from typing import Optional

import bleach
from urllib.parse import urlparse


def sanitize_query(query: str) -> str:
    """Sanitize search query for external APIs.

    Removes control characters and angle brackets while preserving
    useful punctuation for search queries.

    Args:
        query: Raw query string.

    Returns:
        Sanitized query string (max 500 characters).
    """
    if not isinstance(query, str):
        return ""
    q = query.strip()
    # Remove control characters and angle brackets
    q = re.sub(r"[\x00-\x1f<>]", "", q)
    return q[:500]


def _is_allowed_href(href: Optional[str]) -> bool:
    """Check if href uses an allowed URL scheme.

    Args:
        href: URL string to check.

    Returns:
        True if scheme is allowed (http, https, mailto, or empty).
    """
    if not href:
        return False
    try:
        parsed = urlparse(href)
    except Exception:
        return False
    return parsed.scheme in ("http", "https", "mailto", "")


def sanitize_html(content: str) -> str:
    """Sanitize HTML content to prevent XSS attacks.

    Allows a conservative set of tags and attributes, ensures href
    attributes use safe protocols, and adds security attributes to links.

    Args:
        content: HTML content to sanitize.

    Returns:
        Sanitized HTML string.
    """
    if not isinstance(content, str) or not content:
        return ""

    allowed_tags = [
        "p",
        "br",
        "strong",
        "em",
        "u",
        "a",
        "ul",
        "ol",
        "li",
        "span",
        "div",
        "code",
        "pre",
        "blockquote",
    ]
    allowed_attributes = {
        "a": ["href", "title", "rel", "target"],
        "span": ["class"],
        "div": ["class"],
    }

    cleaned = bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True,
    )

    # Post-process hrefs for security
    def replace_href(match: re.Match[str]) -> str:
        href_val = match.group(1)
        if _is_allowed_href(href_val):
            return f'href="{href_val}" target="_blank" rel="noopener noreferrer"'
        return 'href="#"'

    cleaned = re.sub(r'href="([^"]*)"', replace_href, cleaned)

    return cleaned


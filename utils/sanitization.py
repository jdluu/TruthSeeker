import re
import bleach
from urllib.parse import urlparse
from typing import Optional

# Query sanitization: preserve useful punctuation for searches while removing
# control characters and angle brackets that could be misinterpreted as HTML.
def sanitize_query(query: str) -> str:
    """Sanitize the search query for use with external search APIs.

    - Removes control characters and angle brackets.
    - Trims and enforces a 500 character limit.
    - Preserves common search punctuation so queries remain useful.
    """
    if not isinstance(query, str):
        return ""
    q = query.strip()
    # Remove control characters and angle brackets which could break downstream systems
    q = re.sub(r'[\x00-\x1f<>]', '', q)
    return q[:500]


def _is_allowed_href(href: Optional[str]) -> bool:
    """Allow only safe URL schemes for hrefs."""
    if not href:
        return False
    try:
        p = urlparse(href)
    except Exception:
        return False
    # Allow http, https, and mailto links only
    return p.scheme in ("http", "https", "mailto", "")


def sanitize_html(content: str) -> str:
    """Sanitize HTML content to prevent XSS attacks.

    - Allows a conservative set of tags and attributes.
    - Ensures href attributes use safe protocols (http(s) or mailto).
    - Adds rel="noopener noreferrer" and target="_blank" to external links for safety.
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

    # Post-process hrefs to ensure allowed protocols and safe link attributes.
    def replace_href(match: re.Match) -> str:
        href_val = match.group(1)
        if _is_allowed_href(href_val):
            # For external links, ensure they open safely
            return f'href="{href_val}" target="_blank" rel="noopener noreferrer"'
        # Neutralize disallowed hrefs
        return 'href="#"'

    cleaned = re.sub(r'href="([^"]*)"', replace_href, cleaned)

    return cleaned

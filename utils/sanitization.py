import re
import bleach
import html

def sanitize_query(query: str) -> str:
    """Sanitize the search query to prevent injection attacks."""
    sanitized = re.sub(r'[^\w\s-]', '', query)
    return sanitized[:500]

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

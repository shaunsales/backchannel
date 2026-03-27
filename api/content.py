"""
Content processing pipeline for Backchannel.

Converts email/message content to clean markdown with filtering and truncation.
"""
import re
import logging

from markdownify import markdownify as md

log = logging.getLogger(__name__)

# Maximum body size in characters (~50KB). Content beyond this is truncated.
MAX_BODY_CHARS = 50_000

# Minimum ratio of printable characters for content to be considered valid text.
MIN_PRINTABLE_RATIO = 0.85

# Regex patterns for binary/garbage detection
_BASE64_BLOCK = re.compile(r'[A-Za-z0-9+/=]{200,}')
_LONG_HEX_BLOCK = re.compile(r'[0-9a-fA-F]{100,}')
_REPEATED_CHARS = re.compile(r'(.)\1{50,}')


def html_to_markdown(html: str) -> str:
    """Convert HTML email body to clean markdown."""
    if not html or not html.strip():
        return ""

    result = md(
        html,
        heading_style="ATX",
        bullets="-",
        strip=["img", "script", "style", "head", "meta", "link"],
        convert=["p", "a", "strong", "em", "h1", "h2", "h3", "h4", "h5", "h6",
                 "ul", "ol", "li", "br", "blockquote", "pre", "code", "table",
                 "thead", "tbody", "tr", "th", "td", "hr", "b", "i", "u", "s"],
    )

    # Clean up excessive whitespace from HTML conversion
    result = re.sub(r'\n{3,}', '\n\n', result)
    result = re.sub(r'[ \t]+\n', '\n', result)
    result = result.strip()

    return result


def text_to_markdown(plain: str) -> str:
    """Light cleanup of plain text content. Already readable, just normalize."""
    if not plain or not plain.strip():
        return ""

    # Normalize line endings
    result = plain.replace('\r\n', '\n').replace('\r', '\n')

    # Collapse runs of 3+ blank lines to 2
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Strip trailing whitespace per line
    result = re.sub(r'[ \t]+\n', '\n', result)

    return result.strip()


def _is_binary_garbage(text: str) -> bool:
    """Detect if text content is likely binary data rendered as text."""
    if not text:
        return False

    # Check printable character ratio
    printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
    ratio = printable / len(text) if text else 1.0
    if ratio < MIN_PRINTABLE_RATIO:
        return True

    # Check for large base64 blocks
    if _BASE64_BLOCK.search(text):
        return True

    # Check for large hex blocks
    if _LONG_HEX_BLOCK.search(text):
        return True

    return False


def _strip_binary_blocks(text: str) -> str:
    """Remove base64/hex blocks from text while keeping the rest."""
    text = _BASE64_BLOCK.sub('[binary data removed]', text)
    text = _LONG_HEX_BLOCK.sub('[binary data removed]', text)
    text = _REPEATED_CHARS.sub(r'\1' * 3 + '…', text)
    return text


def _truncate(text: str, max_chars: int = MAX_BODY_CHARS) -> str:
    """Truncate text to max_chars, appending a note if truncated."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Try to break at a paragraph or line boundary
    last_para = truncated.rfind('\n\n')
    if last_para > max_chars * 0.8:
        truncated = truncated[:last_para]
    else:
        last_line = truncated.rfind('\n')
        if last_line > max_chars * 0.9:
            truncated = truncated[:last_line]
    return truncated + '\n\n---\n*[Content truncated — original was {:,} characters]*'.format(len(text))


def process_content(body_plain: str = "", body_html: str = "") -> str:
    """
    Main content pipeline: convert email content to clean markdown.

    Priority:
    1. If HTML available → convert to markdown (richer formatting)
    2. If only plain text → light cleanup
    3. Filter binary/garbage content
    4. Truncate if too long

    Returns clean markdown string.
    """
    # Step 1: Convert to markdown
    if body_html and body_html.strip():
        content = html_to_markdown(body_html)
        # If HTML conversion produced nothing useful, fall back to plain
        if not content.strip() and body_plain:
            content = text_to_markdown(body_plain)
    elif body_plain:
        content = text_to_markdown(body_plain)
    else:
        return ""

    if not content.strip():
        return ""

    # Step 2: Filter binary garbage
    if _is_binary_garbage(content):
        log.debug("Content appears to be binary garbage, stripping blocks")
        content = _strip_binary_blocks(content)

    # Step 3: Truncate
    content = _truncate(content)

    return content

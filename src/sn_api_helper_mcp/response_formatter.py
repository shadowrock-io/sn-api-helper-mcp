"""Response formatting layer — optimizes raw API responses for AI agent consumption.

Strategy:
- Parse Elasticsearch hits into individual documents
- Per-document content budget with section-aware truncation
- Code examples preserved intact
- Overall hard cap to protect agent context windows
"""

from __future__ import annotations

import re
from typing import Any

_MAX_CHARS_PER_DOC = 8000
_MAX_TOTAL_CHARS = 30000
_CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```")
_EXCESSIVE_NEWLINES = re.compile(r"\n{3,}")
_HTML_TAG = re.compile(r"<[^>]+>")


def format_search_results(
    hits: list[dict[str, Any]],
    *,
    max_chars_per_doc: int = _MAX_CHARS_PER_DOC,
    max_total_chars: int = _MAX_TOTAL_CHARS,
) -> str:
    """Format a list of Elasticsearch hits for optimal AI agent consumption.

    Each hit is expected to have ``_source.content`` and ``_source.path``.
    Documents are formatted individually with a per-document character budget,
    then combined under an overall hard cap.

    Args:
        hits: List of Elasticsearch hit dicts (``{"_source": {"content": ..., "path": ...}, ...}``).
        max_chars_per_doc: Maximum characters per individual document section.
        max_total_chars: Overall character budget across all documents.

    Returns:
        Clean markdown-formatted string with source attribution headers.
    """
    if not hits:
        return "No results found for this query."

    sections: list[str] = []
    total_chars = 0

    for hit in hits:
        source = hit.get("_source", {})
        content = source.get("content", "")
        path = source.get("path", "unknown")

        if not content or not content.strip():
            continue

        formatted = _format_document(content, path, max_chars_per_doc)
        section_len = len(formatted)

        if total_chars + section_len > max_total_chars:
            remaining = max_total_chars - total_chars
            if remaining > 500:
                formatted = _truncate_at_boundary(formatted, remaining)
                sections.append(formatted)
            break

        sections.append(formatted)
        total_chars += section_len

    if not sections:
        return "No usable content found in search results."

    return "\n\n---\n\n".join(sections)


def _format_document(content: str, path: str, max_chars: int) -> str:
    """Format a single document with source header and content budget."""
    header = f"## Source: `{path}`\n\n"

    text = _strip_html(content)
    text = _normalize_whitespace(text)

    code_blocks = _CODE_BLOCK_PATTERN.findall(text)
    prose = _CODE_BLOCK_PATTERN.sub("{{CODE_BLOCK}}", text)

    content_budget = max_chars - len(header)
    prose = _truncate_at_boundary(prose, content_budget)

    for block in code_blocks:
        prose = prose.replace("{{CODE_BLOCK}}", block, 1)

    leftover_placeholders = prose.count("{{CODE_BLOCK}}")
    for _ in range(leftover_placeholders):
        prose = prose.replace("{{CODE_BLOCK}}", "[code example truncated]", 1)

    return header + prose.strip()


def _strip_html(text: str) -> str:
    """Remove HTML tags while preserving content."""
    return _HTML_TAG.sub("", text)


def _normalize_whitespace(text: str) -> str:
    """Collapse excessive newlines and trailing spaces."""
    text = _EXCESSIVE_NEWLINES.sub("\n\n", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines)


def _truncate_at_boundary(text: str, max_chars: int) -> str:
    """Truncate text at a section boundary rather than mid-sentence.

    Prefers cutting at markdown headers, separators, or paragraph breaks.
    """
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]

    for boundary in ("\n## ", "\n### ", "\n---", "\n\n"):
        last_break = truncated.rfind(boundary)
        if last_break > max_chars * 0.5:
            return truncated[:last_break].rstrip() + "\n\n[... truncated]"

    last_newline = truncated.rfind("\n")
    if last_newline > max_chars * 0.7:
        return truncated[:last_newline].rstrip() + "\n\n[... truncated]"

    return truncated.rstrip() + "\n\n[... truncated]"


# -- Legacy API (backward compatible, deprecated) --


def format_response(raw: str, *, max_chars: int = 4000) -> str:
    """Format a raw API response string. Deprecated — use format_search_results instead.

    Kept for backward compatibility with any code that passes raw text.
    """
    if not raw or not raw.strip():
        return "No information available for this query."

    text = _strip_html(raw)
    text = _normalize_whitespace(text)

    code_blocks = _CODE_BLOCK_PATTERN.findall(text)
    prose = _CODE_BLOCK_PATTERN.sub("{{CODE_BLOCK}}", text)
    prose = _truncate_at_boundary(prose, max_chars)

    for block in code_blocks:
        prose = prose.replace("{{CODE_BLOCK}}", block, 1)

    return prose.strip()

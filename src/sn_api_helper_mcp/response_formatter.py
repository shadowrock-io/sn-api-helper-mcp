"""Response formatting layer — optimizes raw API responses for AI agent consumption.

Strategy: Balanced clarity
- Structured sections with clear labels
- Code examples preserved intact
- Verbose prose trimmed to essentials
- Clean markdown output
"""

from __future__ import annotations

import re

_MAX_PROSE_CHARS = 4000
_CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```")
_EXCESSIVE_NEWLINES = re.compile(r"\n{3,}")
_HTML_TAG = re.compile(r"<[^>]+>")


def format_response(raw: str, *, max_chars: int = _MAX_PROSE_CHARS) -> str:
    """Format a raw API response for optimal AI agent consumption.

    Preserves code blocks intact, trims verbose prose, strips HTML artifacts,
    and normalizes whitespace.

    Args:
        raw: Raw response text from the upstream API.
        max_chars: Maximum character budget for non-code prose sections.

    Returns:
        Clean markdown-formatted string.
    """
    if not raw or not raw.strip():
        return "No information available for this query."

    text = _strip_html(raw)
    text = _normalize_whitespace(text)

    code_blocks = _CODE_BLOCK_PATTERN.findall(text)
    prose = _CODE_BLOCK_PATTERN.sub("{{CODE_BLOCK}}", text)

    prose = _trim_prose(prose, max_chars)

    for block in code_blocks:
        prose = prose.replace("{{CODE_BLOCK}}", block, 1)

    return prose.strip()


def _strip_html(text: str) -> str:
    """Remove HTML tags while preserving content."""
    return _HTML_TAG.sub("", text)


def _normalize_whitespace(text: str) -> str:
    """Collapse excessive newlines and trailing spaces."""
    text = _EXCESSIVE_NEWLINES.sub("\n\n", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines)


def _trim_prose(text: str, max_chars: int) -> str:
    """Trim prose to budget, preserving structure markers like headers."""
    if len(text) <= max_chars:
        return text

    lines = text.splitlines()
    result: list[str] = []
    char_count = 0

    for line in lines:
        is_header = line.lstrip().startswith("#")
        is_placeholder = "{{CODE_BLOCK}}" in line
        is_separator = line.strip() in ("---", "***", "___")

        if is_header or is_placeholder or is_separator:
            result.append(line)
            char_count += len(line) + 1
            continue

        if char_count + len(line) + 1 > max_chars:
            result.append("...")
            break

        result.append(line)
        char_count += len(line) + 1

    return "\n".join(result)

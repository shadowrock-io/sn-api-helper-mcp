"""Response formatting layer — optimizes raw API responses for AI agent consumption.

Strategy:
- Parse Elasticsearch hits into individual documents
- Query-aware content extraction: OpenAPI endpoint matching + markdown section reordering
- Per-document content budget with section-aware truncation
- Code examples preserved intact
- Overall hard cap to protect agent context windows
"""

from __future__ import annotations

import json
import re
from typing import Any

_MAX_CHARS_PER_DOC = 8000
_MAX_TOTAL_CHARS = 30000
_CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```")
_EXCESSIVE_NEWLINES = re.compile(r"\n{3,}")
_HTML_TAG = re.compile(r"<[^>]+>")
_SECTION_HEADER = re.compile(r"^#{2,4}\s+.+$", re.MULTILINE)

_HTTP_METHODS = frozenset({"get", "post", "put", "delete", "patch", "head", "options"})
_STOP_WORDS = frozenset(
    {"the", "a", "an", "for", "to", "in", "of", "and", "or", "with", "by", "is", "it"}
)


# ── Query tokenization ──


def _tokenize_query(query: str) -> tuple[set[str], set[str]]:
    """Split query into (keyword_tokens, http_method_tokens).

    Returns a tuple of (keywords, methods) where keywords are the meaningful
    content words and methods are any HTTP verbs found in the query.
    """
    tokens = set(query.lower().split())
    methods = tokens & _HTTP_METHODS
    keywords = tokens - _HTTP_METHODS - _STOP_WORDS
    # Remove very short tokens (likely noise)
    keywords = {k for k in keywords if len(k) > 1}
    return keywords, methods


# ── OpenAPI endpoint extraction ──


def _extract_from_json_spec(
    content: str,
    query: str,
    budget: int,
) -> str | None:
    """Try to extract relevant endpoints from an OpenAPI JSON spec.

    Parses the content as JSON, looks for an OpenAPI-style ``paths`` structure,
    scores each endpoint against the query, and returns the best matches
    formatted as readable markdown.  Returns ``None`` if the content is not
    parseable JSON or has no ``paths`` key.
    """
    try:
        spec = json.loads(content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None

    if not isinstance(spec, dict):
        return None

    paths = spec.get("paths", {})
    if not paths or not isinstance(paths, dict):
        return None

    keywords, method_filter = _tokenize_query(query)
    if not keywords:
        return None

    scored: list[tuple[float, str, str, dict[str, Any]]] = []

    for path_str, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        path_lower = path_str.lower()
        # Extract path segments, excluding parameters like {id}
        segments = {s for s in path_lower.strip("/").split("/") if not s.startswith("{")}

        # Score path by keyword overlap with segments and full path
        path_score = sum(2.0 for kw in keywords if kw in segments)
        path_score += sum(1.0 for kw in keywords if kw in path_lower)

        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue

            op_score = path_score

            # Boost if query specifies this HTTP method
            if method_filter and method.lower() in method_filter:
                op_score += 3.0

            summary = operation.get("summary", "").lower()
            description = operation.get("description", "").lower()
            op_id = operation.get("operationId", "").lower()

            op_score += sum(2.0 for kw in keywords if kw in summary)
            op_score += sum(1.0 for kw in keywords if kw in description)
            op_score += sum(1.0 for kw in keywords if kw in op_id)

            if op_score > 0:
                scored.append((op_score, method.upper(), path_str, operation))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)

    # Format top endpoints within budget
    parts: list[str] = []
    total_len = 0

    for _, method, path_str, operation in scored[:5]:
        endpoint_md = _format_endpoint(method, path_str, operation)

        if total_len + len(endpoint_md) > budget:
            if parts:
                break
            # First endpoint always included, truncated if needed
            endpoint_md = _truncate_at_boundary(endpoint_md, budget)

        parts.append(endpoint_md)
        total_len += len(endpoint_md)

    return "\n\n---\n\n".join(parts)


def _format_endpoint(
    method: str,
    path: str,
    operation: dict[str, Any],
) -> str:
    """Format a single OpenAPI endpoint as readable markdown."""
    lines = [f"### `{method} {path}`"]

    if summary := operation.get("summary"):
        lines.append(f"\n{summary}")

    if description := operation.get("description"):
        if len(description) > 500:
            description = description[:500] + "..."
        lines.append(f"\n{description}")

    # Parameters
    params = operation.get("parameters", [])
    if isinstance(params, list) and params:
        lines.append("\n**Parameters:**\n")
        for p in params:
            if not isinstance(p, dict):
                continue
            name = p.get("name", "?")
            location = p.get("in", "?")
            required = "required" if p.get("required") else "optional"
            desc = p.get("description", "")
            p_type = ""
            schema = p.get("schema", {})
            if isinstance(schema, dict):
                p_type = schema.get("type", "")
            type_str = f", {p_type}" if p_type else ""
            param_line = f"- `{name}` ({location}{type_str}, {required})"
            if desc:
                param_line += f": {desc}"
            lines.append(param_line)

    # Request body
    body = operation.get("requestBody", {})
    if isinstance(body, dict) and body:
        lines.append("\n**Request Body:**\n")
        body_content = body.get("content", {})
        if isinstance(body_content, dict):
            for media_type, media_obj in body_content.items():
                if not isinstance(media_obj, dict):
                    continue
                schema = media_obj.get("schema", {})
                if schema:
                    schema_str = json.dumps(schema, indent=2)
                    if len(schema_str) > 1500:
                        schema_str = schema_str[:1500] + "\n  ..."
                    lines.append(f"Content-Type: `{media_type}`")
                    lines.append(f"```json\n{schema_str}\n```")

    # Responses
    responses = operation.get("responses", {})
    if isinstance(responses, dict) and responses:
        lines.append("\n**Responses:**\n")
        for code, resp in sorted(responses.items()):
            if not isinstance(resp, dict):
                continue
            desc = resp.get("description", "")
            lines.append(f"- `{code}`: {desc}")

    return "\n".join(lines)


# ── Markdown section reordering ──


def _reorder_sections_by_relevance(text: str, keywords: set[str]) -> str:
    """Reorder markdown sections so the most query-relevant content appears first.

    Splits the text at ``##``/``###``/``####`` headers, scores each section
    by keyword density, and reassembles with the highest-scoring section first.
    The preamble (content before the first header) stays at the top.
    """
    if not keywords:
        return text

    matches = list(_SECTION_HEADER.finditer(text))
    if not matches:
        return text

    preamble = text[: matches[0].start()]
    sections: list[str] = []

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(text[start:end])

    if len(sections) <= 1:
        return text

    scored: list[tuple[float, int, str]] = []
    for idx, section in enumerate(sections):
        section_lower = section.lower()
        score = sum(section_lower.count(kw) for kw in keywords)
        # Use original index as tiebreaker for stable ordering
        scored.append((score, idx, section))

    scored.sort(key=lambda x: (-x[0], x[1]))

    return preamble + "".join(s for _, _, s in scored)


# ── Core formatting pipeline ──


def format_search_results(
    hits: list[dict[str, Any]],
    *,
    query: str = "",
    max_chars_per_doc: int = _MAX_CHARS_PER_DOC,
    max_total_chars: int = _MAX_TOTAL_CHARS,
) -> str:
    """Format a list of Elasticsearch hits for optimal AI agent consumption.

    Each hit is expected to have ``_source.content`` and ``_source.path``.
    Documents are formatted individually with a per-document character budget,
    then combined under an overall hard cap.

    When ``query`` is provided, content extraction is query-aware:
    - JSON API specs: extracts the specific endpoint(s) matching the query
    - Markdown docs: reorders sections so the most relevant appears first

    Args:
        hits: List of Elasticsearch hit dicts.
        query: Original search query for content-aware extraction.
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

        formatted = _format_document(content, path, max_chars_per_doc, query=query)
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


def _format_document(
    content: str,
    path: str,
    max_chars: int,
    *,
    query: str = "",
) -> str:
    """Format a single document with source header and content budget.

    For JSON API specs (path ending in ``.json``), attempts to extract
    the specific endpoint matching the query before falling back to
    generic text formatting.
    """
    header = f"## Source: `{path}`\n\n"
    content_budget = max_chars - len(header)

    # For JSON API specs, try endpoint extraction first
    if path.endswith(".json") and query:
        extracted = _extract_from_json_spec(content, query, content_budget)
        if extracted:
            return header + extracted

    text = _strip_html(content)
    text = _normalize_whitespace(text)

    # Reorder sections by query relevance before truncation
    if query:
        keywords, _ = _tokenize_query(query)
        text = _reorder_sections_by_relevance(text, keywords)

    code_blocks = _CODE_BLOCK_PATTERN.findall(text)
    prose = _CODE_BLOCK_PATTERN.sub("{{CODE_BLOCK}}", text)

    prose = _truncate_at_boundary(prose, content_budget)

    for block in code_blocks:
        prose = prose.replace("{{CODE_BLOCK}}", block, 1)

    leftover_placeholders = prose.count("{{CODE_BLOCK}}")
    for _ in range(leftover_placeholders):
        prose = prose.replace("{{CODE_BLOCK}}", "[code example truncated]", 1)

    return header + prose.strip()


# ── Text processing utilities ──


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

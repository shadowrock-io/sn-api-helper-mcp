"""Argument completion handler for SignNow API tools, resources, and prompts."""

from __future__ import annotations

from typing import Any

from mcp.types import Completion, PromptReference, ResourceTemplateReference

_COMMON_QUERIES = [
    "embedded signing",
    "free form invite",
    "OAuth2 authentication",
    "document templates",
    "webhook events",
    "bulk send",
    "document groups",
    "field invite",
    "prefill fields",
    "download document",
    "create document from template",
    "signing link",
    "role-based invite",
    "text tags",
    "branding",
]

_LANGUAGES = ["python", "node", "php", "java", "csharp", "ruby", "go"]

_USE_CASES = [
    "embedded signing",
    "bulk send",
    "template management",
    "document generation",
    "webhook integration",
    "white-label signing",
]

_GUIDE_TOPICS = [
    "embedded-signing",
    "bulk-send",
    "template-management",
    "webhook-integration",
    "document-fields",
    "branding",
]


def _filter_values(values: list[str], partial: str) -> list[str]:
    """Filter values by partial prefix match."""
    lower = partial.lower()
    return [v for v in values if lower in v.lower()][:20]


def register_completions(mcp: Any) -> None:
    """Register the completion handler on the MCP server."""

    @mcp.completion()
    async def handle_completion(
        ref: PromptReference | ResourceTemplateReference,
        argument: Any,
        context: Any = None,
    ) -> Completion | None:
        name = argument.name
        partial = argument.value or ""

        if isinstance(ref, PromptReference):
            if name == "language":
                return Completion(values=_filter_values(_LANGUAGES, partial))
            if name == "use_case":
                return Completion(values=_filter_values(_USE_CASES, partial))
            if name == "grant_type":
                return Completion(
                    values=_filter_values(["authorization_code", "password"], partial)
                )
            if name in ("status_code", "error_message", "endpoint"):
                return None

        if isinstance(ref, ResourceTemplateReference) and name == "topic":
            return Completion(values=_filter_values(_GUIDE_TOPICS, partial))

        if name == "query":
            return Completion(values=_filter_values(_COMMON_QUERIES, partial))

        return None

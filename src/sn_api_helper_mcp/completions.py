"""Argument completion handler for SignNow API tools, resources, and prompts."""

from __future__ import annotations

from typing import Any

from mcp.types import Completion, PromptReference, ResourceTemplateReference

# Query suggestions follow the pattern: {HTTP_METHOD} {resource} {action}
# for endpoint specs, or {feature} guide for walkthroughs.
_COMMON_QUERIES = [
    "POST embedded signing invite",
    "POST free form invite",
    "PUT document fields add signature text",
    "POST template bulkinvite",
    "GET document download signed PDF",
    "POST OAuth2 token endpoint password grant",
    "POST webhook event subscription callback",
    "POST create document from template",
    "GET document fields list",
    "POST role-based invite",
    "POST prefill smart fields merge",
    "POST document group invite",
    "embedded signing setup guide",
    "text tags guide",
    "branding guide",
]

_CONTENT_TYPE_VALUES = ["all", "api-spec", "guide", "integration"]

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

_MAX_RESULTS_VALUES = ["1", "2", "3", "5", "10"]


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

        if name == "max_results":
            return Completion(values=_filter_values(_MAX_RESULTS_VALUES, partial))

        if name == "content_type":
            return Completion(values=_filter_values(_CONTENT_TYPE_VALUES, partial))

        return None

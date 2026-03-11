"""SignNow API information tool — async, structured output, cached.

Queries the upstream Elasticsearch-backed documentation API and returns
the most relevant results with per-document budgets and overall hard caps
to protect agent context windows.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

import httpx
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..cache import TTLCache
from ..response_formatter import format_search_results

_API_URL = "https://integrations-copilot.signnow.com/api/skills/getInfo"
_TIMEOUT = 30.0
_MAX_RETRIES = 2
_DEFAULT_MAX_RESULTS = 3
_MIN_SCORE_RATIO = 0.5

_log = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=900.0)
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
    return _http_client


class SignNowApiInfo(BaseModel):
    """Structured response from the SignNow API documentation search."""

    query: str = Field(description="The original search query")
    content: str = Field(description="Formatted API documentation content (markdown)")
    result_count: int = Field(description="Number of documentation sections returned")
    total_available: int = Field(description="Total matching documents in the knowledge base")
    sources: list[str] = Field(description="Source paths of included documentation sections")
    source: str = Field(
        default="SignNow API Documentation",
        description="Information source identifier",
    )


def _extract_top_hits(
    data: dict[str, Any],
    *,
    max_results: int,
) -> tuple[list[dict[str, Any]], int]:
    """Extract and filter the most relevant hits from an Elasticsearch response.

    Applies a minimum relevance score threshold: hits scoring below 50% of the
    top hit's score are excluded to avoid tangential results.

    Returns:
        Tuple of (filtered hits list, total available count).
    """
    hits_wrapper = data.get("hits", data)

    if isinstance(hits_wrapper, dict):
        hit_list = hits_wrapper.get("hits", [])
        total_raw = hits_wrapper.get("total", {})
        total_available = (
            total_raw.get("value", len(hit_list))
            if isinstance(total_raw, dict)
            else int(total_raw)
            if total_raw
            else len(hit_list)
        )
    elif isinstance(hits_wrapper, list):
        hit_list = hits_wrapper
        total_available = len(hit_list)
    else:
        return [], 0

    if not hit_list:
        return [], total_available

    top_score = hit_list[0].get("_score", 1.0) if hit_list else 1.0
    threshold = top_score * _MIN_SCORE_RATIO if top_score else 0

    filtered: list[dict[str, Any]] = []
    for hit in hit_list:
        if len(filtered) >= max_results:
            break
        score = hit.get("_score", 0)
        if score is not None and score >= threshold:
            filtered.append(hit)

    return filtered, total_available


def _cache_key(query: str, max_results: int) -> str:
    return f"{query.strip().lower()}::max={max_results}"


def bind(mcp: Any) -> None:
    @mcp.tool(
        name="get_signnow_api_info",
        description=(
            "Get information about SignNow API. This is documentation for API usage. "
            "Use specific queries like 'OAuth2 token endpoint', 'embedded signing invite', "
            "'document field invite', or 'download signed PDF' rather than broad topics "
            "like 'authentication' or 'signing'. Returns the top matching documentation "
            "sections with endpoint details, parameters, code examples, and error handling "
            "guidance. Adjust max_results (1-5) to control breadth: use 1 for focused "
            "answers, 3 (default) for standard lookups, 5 when exploring broadly."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def get_signnow_api_info(
        ctx: Context,
        query: Annotated[
            str,
            Field(
                description=(
                    "Query string to search for API information (e.g., 'free form invite')"
                ),
            ),
        ],
        max_results: Annotated[
            int,
            Field(
                default=_DEFAULT_MAX_RESULTS,
                ge=1,
                le=10,
                description=(
                    "Maximum number of documentation sections to return (1-10). "
                    "Use 1 for focused answers, 3 for standard lookups, "
                    "5+ when exploring a topic broadly."
                ),
            ),
        ] = _DEFAULT_MAX_RESULTS,
    ) -> SignNowApiInfo:
        """Query the SignNow API documentation endpoint.

        Searches the SignNow knowledge base and returns the most relevant
        documentation sections, filtered by relevance score, with per-document
        character budgets and an overall hard cap for context-efficient responses.
        """
        key = _cache_key(query, max_results)

        cached = _cache.get(key)
        if cached is not None:
            await ctx.info(f"Cache hit for query: {query}")
            return cached

        await ctx.info(f"Querying SignNow API docs: {query}")

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                client = _get_client()
                response = await client.post(
                    _API_URL,
                    json={"query": query},
                )
                response.raise_for_status()

                data = response.json()
                hits, total_available = _extract_top_hits(data, max_results=max_results)

                formatted_content = format_search_results(hits)
                sources = [hit.get("_source", {}).get("path", "unknown") for hit in hits]

                result = SignNowApiInfo(
                    query=query,
                    content=formatted_content,
                    result_count=len(hits),
                    total_available=total_available,
                    sources=sources,
                )

                _cache.set(key, result)
                return result

            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                if status in (429, 503) and attempt < _MAX_RETRIES:
                    await ctx.warning(
                        f"Retryable error (HTTP {status}), attempt {attempt + 1}/{_MAX_RETRIES}"
                    )
                    continue
                await ctx.error(f"HTTP error {status} querying SignNow API")
                return SignNowApiInfo(
                    query=query,
                    content=(f"Error: HTTP {status} from SignNow API. {exc.response.text[:200]}"),
                    result_count=0,
                    total_available=0,
                    sources=[],
                )

            except httpx.TimeoutException:
                last_error = httpx.TimeoutException("Request timed out")
                if attempt < _MAX_RETRIES:
                    await ctx.warning(f"Timeout, retrying ({attempt + 1}/{_MAX_RETRIES})")
                    continue
                await ctx.error("SignNow API request timed out after retries")
                return SignNowApiInfo(
                    query=query,
                    content=("Error: SignNow API request timed out. Try a more specific query."),
                    result_count=0,
                    total_available=0,
                    sources=[],
                )

            except httpx.RequestError as exc:
                last_error = exc
                await ctx.error(f"Network error: {exc}")
                return SignNowApiInfo(
                    query=query,
                    content=f"Error: Network error connecting to SignNow API — {exc}",
                    result_count=0,
                    total_available=0,
                    sources=[],
                )

        error_msg = str(last_error) if last_error else "Unknown error"
        return SignNowApiInfo(
            query=query,
            content=(f"Error: Failed after {_MAX_RETRIES + 1} attempts — {error_msg}"),
            result_count=0,
            total_available=0,
            sources=[],
        )

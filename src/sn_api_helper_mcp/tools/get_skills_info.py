"""SignNow API information tool — async, structured output, cached.

Queries the upstream Elasticsearch-backed documentation API and returns
the most relevant results with client-side re-ranking by content type,
per-document budgets, and overall hard caps to protect agent context windows.

The upstream ES index contains a mix of API reference specs (OpenAPI JSON),
core feature guides (markdown), and third-party integration guides (Salesforce,
NetSuite, QuickBooks, Power Automate).  Because the ES relevance model can't
distinguish developer intent, we apply path-based boost factors client-side
so that API specs surface above integration walkthroughs for the same query.
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


# ── Content-type classification and boost factors ──

CONTENT_TYPE_API_SPEC = "api-spec"
CONTENT_TYPE_GUIDE = "guide"
CONTENT_TYPE_INTEGRATION = "integration"
CONTENT_TYPE_OTHER = "other"

VALID_CONTENT_TYPES = frozenset(
    {"all", CONTENT_TYPE_API_SPEC, CONTENT_TYPE_GUIDE, CONTENT_TYPE_INTEGRATION}
)

# Paths that are high-keyword-density noise for most developer queries.
_NOISE_PATHS = frozenset(
    {
        "docs/sn/changelog.md",
        "docs/sn/guides/ai_tools/signnow-mcp-server.md",
    }
)

# Boost multipliers applied to the raw ES score before re-ranking.
# Values > 1.0 promote, < 1.0 demote.
_BOOST_FACTORS: dict[str, float] = {
    CONTENT_TYPE_API_SPEC: 1.5,
    CONTENT_TYPE_GUIDE: 1.0,
    CONTENT_TYPE_INTEGRATION: 0.3,
    CONTENT_TYPE_OTHER: 0.7,
}

_NOISE_BOOST = 0.1


def _classify_content_type(path: str) -> str:
    """Classify a document by its index path into a content type."""
    if path.startswith("reference/"):
        return CONTENT_TYPE_API_SPEC
    if path.startswith("docs/integration/"):
        return CONTENT_TYPE_INTEGRATION
    if path.startswith("docs/sn/guides/"):
        return CONTENT_TYPE_GUIDE
    return CONTENT_TYPE_OTHER


def _content_boost(path: str) -> float:
    """Return a score multiplier for a document based on its path.

    API reference specs are boosted, integration guides demoted, and
    known noise documents (changelog, MCP meta-doc) heavily penalised.
    """
    if path in _NOISE_PATHS:
        return _NOISE_BOOST
    content_type = _classify_content_type(path)
    return _BOOST_FACTORS.get(content_type, 0.7)


# ── HTTP client ──


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
    return _http_client


# ── Response model ──


class SignNowApiInfo(BaseModel):
    """Structured response from the SignNow API documentation search."""

    query: str = Field(description="The original search query")
    content: str = Field(description="Formatted API documentation content (markdown)")
    result_count: int = Field(description="Number of documentation sections returned")
    total_available: int = Field(
        description="Total matching documents in the knowledge base (before content-type filtering)"
    )
    sources: list[str] = Field(description="Source paths of included documentation sections")
    source: str = Field(
        default="SignNow API Documentation",
        description="Information source identifier",
    )


# ── Hit extraction and re-ranking ──


def _extract_top_hits(
    data: dict[str, Any],
    *,
    max_results: int,
    content_type: str = "all",
) -> tuple[list[dict[str, Any]], int]:
    """Extract, re-rank, and filter the most relevant hits.

    Pipeline:
    1. Parse the ES response to extract the hit list and total count.
    2. If content_type is not "all", remove hits that don't match.
    3. Compute adjusted scores using path-based boost factors.
    4. Re-sort by adjusted score (descending).
    5. Apply the 50%-of-top threshold to cut tangential results.
    6. Return the top ``max_results`` hits.
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

    # Step 2: content-type filtering (before re-ranking).
    if content_type != "all":
        hit_list = [
            h
            for h in hit_list
            if _classify_content_type(h.get("_source", {}).get("path", "")) == content_type
        ]
        if not hit_list:
            return [], total_available

    # Step 3-4: compute adjusted scores and re-sort.
    scored: list[tuple[float, dict[str, Any]]] = []
    for hit in hit_list:
        raw_score = hit.get("_score", 0) or 0
        path = hit.get("_source", {}).get("path", "")
        adjusted = raw_score * _content_boost(path)
        scored.append((adjusted, hit))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    # Step 5: threshold on adjusted scores.
    top_adjusted = scored[0][0] if scored else 0
    threshold = top_adjusted * _MIN_SCORE_RATIO if top_adjusted else 0

    # Step 6: collect top N above threshold.
    filtered: list[dict[str, Any]] = []
    for adjusted_score, hit in scored:
        if len(filtered) >= max_results:
            break
        if adjusted_score >= threshold:
            filtered.append(hit)

    return filtered, total_available


def _cache_key(query: str, max_results: int, content_type: str = "all") -> str:
    return f"{query.strip().lower()}::max={max_results}::type={content_type}"


# ── Tool binding ──


def bind(mcp: Any) -> None:
    @mcp.tool(
        name="get_signnow_api_info",
        description=(
            "Get information about SignNow API. This is documentation for API usage. "
            "For best results, include HTTP methods and resource nouns in queries: "
            "'POST embedded signing invite', 'PUT document fields add signature', "
            "'OAuth2 token endpoint password grant', 'webhook event subscription callback'. "
            "Avoid broad single-word queries like 'authentication' or 'download'. "
            "Set content_type to 'api-spec' for OpenAPI endpoint specs with parameters "
            "and schemas, 'guide' for feature walkthroughs, 'integration' for "
            "Salesforce/NetSuite/QuickBooks guides, or 'all' (default) for ranked results "
            "across all content types. Adjust max_results (1-5) to control breadth."
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
                    "Search query for API documentation. Best patterns: "
                    "'{HTTP_METHOD} {resource} {action}' for endpoint specs "
                    "(e.g., 'POST template bulkinvite', 'GET document download'), "
                    "'{feature} guide' for walkthroughs "
                    "(e.g., 'text tags guide', 'embedded signing setup')."
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
        content_type: Annotated[
            str,
            Field(
                default="all",
                description=(
                    "Filter results by content type. "
                    "'api-spec': OpenAPI/Swagger endpoint specs with parameters and schemas. "
                    "'guide': Core SignNow feature guides and walkthroughs. "
                    "'integration': Platform-specific guides (Salesforce, NetSuite, etc.). "
                    "'all': All types, ranked with API specs boosted (default)."
                ),
            ),
        ] = "all",
    ) -> SignNowApiInfo:
        """Query the SignNow API documentation endpoint.

        Searches the SignNow knowledge base and returns the most relevant
        documentation sections.  Results are re-ranked client-side so that
        API reference specs surface above integration guides, and known
        noise documents (changelog, MCP meta-doc) are suppressed.
        """
        effective_type = content_type if content_type in VALID_CONTENT_TYPES else "all"
        key = _cache_key(query, max_results, effective_type)

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
                hits, total_available = _extract_top_hits(
                    data,
                    max_results=max_results,
                    content_type=effective_type,
                )

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

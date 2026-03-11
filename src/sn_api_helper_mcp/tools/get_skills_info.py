"""SignNow API information tool — async, structured output, cached."""

from __future__ import annotations

from typing import Annotated, Any

import httpx
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..cache import TTLCache
from ..response_formatter import format_response

_API_URL = "https://integrations-copilot.signnow.com/api/skills/getInfo"
_TIMEOUT = 30.0
_MAX_RETRIES = 2

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
    """Structured response from the SignNow API helper."""

    query: str = Field(description="The original search query")
    content: str = Field(description="Formatted API documentation content")
    source: str = Field(default="SignNow API Documentation", description="Information source")


class SignNowApiError(BaseModel):
    """Structured error response."""

    query: str = Field(description="The original search query")
    error: str = Field(description="Error description")
    status_code: int | None = Field(default=None, description="HTTP status code if applicable")
    suggestion: str = Field(description="Suggested next step for the agent")


def bind(mcp: Any) -> None:
    @mcp.tool(
        name="get_signnow_api_info",
        description=(
            "Get information about SignNow API. This is documentation for API usage. "
            "Returns endpoint details, parameters, code examples, and error handling guidance."
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
                description="Query string to search for API information (e.g., 'free form invite')",
            ),
        ],
    ) -> SignNowApiInfo:
        """Query the SignNow API documentation endpoint.

        Args:
            query: Search query for API information.

        Returns:
            Structured response with formatted documentation content.
        """
        normalized_query = query.strip().lower()

        cached = _cache.get(normalized_query)
        if cached is not None:
            await ctx.info(f"Cache hit for query: {query}")
            return SignNowApiInfo(query=query, content=cached)

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

                raw_text = response.text
                formatted = format_response(raw_text)

                _cache.set(normalized_query, formatted)

                return SignNowApiInfo(query=query, content=formatted)

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
                    content=f"Error: HTTP {status} from SignNow API. {exc.response.text[:200]}",
                )

            except httpx.TimeoutException:
                last_error = httpx.TimeoutException("Request timed out")
                if attempt < _MAX_RETRIES:
                    await ctx.warning(f"Timeout, retrying ({attempt + 1}/{_MAX_RETRIES})")
                    continue
                await ctx.error("SignNow API request timed out after retries")
                return SignNowApiInfo(
                    query=query,
                    content="Error: SignNow API request timed out. Try a more specific query.",
                )

            except httpx.RequestError as exc:
                last_error = exc
                await ctx.error(f"Network error: {exc}")
                return SignNowApiInfo(
                    query=query,
                    content=f"Error: Network error connecting to SignNow API — {exc}",
                )

        error_msg = str(last_error) if last_error else "Unknown error"
        return SignNowApiInfo(
            query=query,
            content=f"Error: Failed after {_MAX_RETRIES + 1} attempts — {error_msg}",
        )

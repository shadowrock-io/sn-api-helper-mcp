"""MCP server setup and capability registration."""

from mcp.server.fastmcp import FastMCP

from .completions import register_completions
from .prompts import register_prompts
from .resources import register_resources
from .tools import register_tools

_INSTRUCTIONS = (
    "SignNow API Helper — provides REST API documentation, code examples, "
    "authentication guidance, and integration patterns. "
    "Use specific queries like 'create embedded signing link', "
    "'OAuth2 authentication flow', or 'document template management'. "
    "Results include endpoint details, parameters, code examples, and error handling. "
    "Static resources are available for quick reference on authentication, base URLs, "
    "error codes, rate limits, and webhooks."
)


def create_server() -> FastMCP:
    """Create and configure the MCP server instance."""
    mcp = FastMCP(
        "sn-api-helper-mcp",
        instructions=_INSTRUCTIONS,
        json_response=True,
        stateless_http=True,
    )
    register_tools(mcp)
    register_resources(mcp)
    register_prompts(mcp)
    register_completions(mcp)
    return mcp

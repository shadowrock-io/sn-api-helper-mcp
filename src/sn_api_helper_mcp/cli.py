"""CLI entrypoint for the MCP server."""

import logging
import sys

import typer

from ._version import __version__
from .server import create_server

app = typer.Typer(help="SignNow API Helper MCP server")


@app.command()
def serve(
    transport: str = typer.Option(
        "streamable-http",
        help="Transport protocol: streamable-http (default), stdio, sse",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        help="Host for HTTP transports",
    ),
    port: int = typer.Option(
        8000,
        help="Port for HTTP transports",
    ),
) -> None:
    """Run the SignNow API Helper MCP server."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    print(
        f"sn-api-helper-mcp v{__version__} | transport={transport}",
        file=sys.stderr,
    )

    mcp = create_server()

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run(transport="streamable-http", host=host, port=port)


def main() -> None:
    app()

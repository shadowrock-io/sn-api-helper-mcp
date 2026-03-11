"""MCPB entry point — runs the MCP server in stdio mode for Desktop Extensions."""

from .server import create_server


def main() -> None:
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

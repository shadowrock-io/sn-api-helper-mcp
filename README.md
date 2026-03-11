# SignNow API Helper MCP
[![PyPI](https://img.shields.io/pypi/v/sn-api-helper-mcp)](https://pypi.org/project/sn-api-helper-mcp/)
[![License](https://img.shields.io/github/license/signnow/sn-api-helper-mcp)](https://github.com/signnow/sn-api-helper-mcp/blob/main/LICENSE.md)

An MCP server for SignNow API helper tools, resources, and prompts.

mcp-name: io.github.signnow/sn-api-helper-mcp

## Purpose & Capabilities

The SignNow API Helper MCP server is a Model Context Protocol server designed to assist AI agents with SignNow API integration. It provides contextual documentation, code examples, and integration guidance.

**Core Functions:**

- **API Documentation Access:** Query the SignNow API documentation for endpoints, parameters, and usage patterns.
- **Code Examples:** Retrieve sample code for common SignNow API operations.
- **Authentication Help:** Reference guides for OAuth2 flows, token management, and required headers.
- **Integration Guidance:** Prompt templates for planning signing workflows, debugging errors, and setting up auth.
- **Error Resolution:** Error code reference and debugging prompts for common API issues.

---

## Installation

To install locally for development:

```bash
pip install -e ".[dev]"
```

## Run

You can run the server using Python or `uvx`. The server supports three transports: **streamable-http** (default), **stdio**, and **sse**.

**Method 1: Python module**

```bash
python -m sn_api_helper_mcp                          # streamable-http on :8000
python -m sn_api_helper_mcp --transport stdio         # stdio for MCP clients
python -m sn_api_helper_mcp --transport sse --port 9000
```

**Method 2: Installed CLI entry point**

```bash
sn-api-helper-mcp                                     # streamable-http on :8000
sn-api-helper-mcp --transport stdio
```

**Method 3: UVX**

```bash
uvx sn-api-helper-mcp
```

---

## Integrations & Setup

You can use this server with any MCP client. Below are configurations for popular IDEs and apps.

### Claude Desktop

1. Open your config file:
    - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
    - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
2. Add the following:

```json
{
  "mcpServers": {
    "signnow-api-helper": {
      "command": "uvx",
      "args": ["sn-api-helper-mcp"]
    }
  }
}
```

3. Restart Claude Desktop.

### Claude Code

Add to your project's `.mcp.json` or global settings:

```json
{
  "mcpServers": {
    "signnow-api-helper": {
      "command": "uvx",
      "args": ["sn-api-helper-mcp"],
      "type": "stdio"
    }
  }
}
```

### Cursor AI

1. Open **Cursor Settings** (`Cmd/Ctrl + ,`).
2. Go to **Features** > **MCP Servers** > **+ Add New MCP Server**.
3. Add:

```json
{
  "mcpServers": {
    "signnow-api-helper": {
      "command": "uvx",
      "args": ["sn-api-helper-mcp"]
    }
  }
}
```

### VS Code (via Cline)

1. Install the **Cline** extension.
2. Open Cline settings > **MCP Servers**.
3. Add:

```json
{
  "signnow-api-helper": {
    "command": "uvx",
    "args": ["sn-api-helper-mcp"]
  }
}
```

---

## Features

### Tools

| Tool | Description |
|------|-------------|
| `get_signnow_api_info` | Query SignNow API documentation. Returns endpoint details, parameters, code examples, and error handling guidance. |

Tool annotations: `readOnlyHint=true`, `idempotentHint=true`, `destructiveHint=false`. Responses use structured output via `json_response`.

### Resources

Static reference data available to MCP clients:

| URI | Description |
|-----|-------------|
| `signnow://api/authentication` | OAuth2 flows, token endpoints, required headers |
| `signnow://api/base-urls` | Production and sandbox URLs, API versioning |
| `signnow://api/error-codes` | HTTP status codes, error response format, common scenarios |
| `signnow://api/rate-limits` | Default limits, rate limit headers, best practices |
| `signnow://api/webhooks` | Event types, payload format, setup, security |

### Prompts

Reusable prompt templates for common integration tasks:

| Prompt | Description |
|--------|-------------|
| `signnow_integration` | Generate a step-by-step integration plan for a use case and language |
| `signnow_auth_setup` | OAuth2 authentication setup guide for a given language and grant type |
| `signnow_error_debug` | Debug a SignNow API error given status code, message, and endpoint |

### Completions

Argument autocompletion for tool queries, prompt parameters, and resource template arguments. Provides suggestions for common API queries, supported languages, use cases, and guide topics.

---

## Development

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Setup

```bash
uv sync --all-extras
```

### Run Tests

```bash
uv run pytest tests/ -v
```

### Lint & Format

```bash
uv run ruff check src/ scripts/ tests/
uv run ruff format src/ scripts/ tests/
```

### MCP Spec Validation

Run the built-in spec compliance validator:

```bash
PYTHONPATH=src uv run python scripts/validate_mcp_spec.py
```

This starts the server via stdio, sends JSON-RPC requests to validate compliance with the MCP specification, and generates a coverage report.

---

## Architecture

```
src/sn_api_helper_mcp/
  cli.py              # Typer CLI — serve command with transport selection
  server.py           # FastMCP server factory with json_response + stateless_http
  cache.py            # In-memory TTL cache for API responses
  response_formatter.py  # Response optimization for AI agent consumption
  completions.py      # Argument completion handler
  tools/
    get_skills_info.py  # Async tool with structured Pydantic output, retries, caching
  resources/
    api_reference.py    # Static SignNow API reference resources
  prompts/
    integration.py      # Integration, auth, and error debugging prompt templates
```

## License

MIT

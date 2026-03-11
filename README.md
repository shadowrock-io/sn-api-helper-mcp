# SignNow API Helper MCP

[![License](https://img.shields.io/github/license/signnow/sn-api-helper-mcp)](https://github.com/signnow/sn-api-helper-mcp/blob/main/LICENSE.md)

A modernized MCP server for SignNow API documentation, code examples, and integration guidance for AI agents. Built and maintained by [ShadowRock](https://github.com/shadowrock-io), originally forked from [signnow/sn-api-helper-mcp](https://github.com/signnow/sn-api-helper-mcp).

mcp-name: io.github.signnow/sn-api-helper-mcp

---

## Install for Claude Desktop

[![Install Claude Desktop Extension](https://img.shields.io/badge/Install-Claude_Desktop_Extension-blue?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTIxIDE1djRhMiAyIDAgMCAxLTIgMkg1YTIgMiAwIDAgMS0yLTJ2LTQiLz48cG9seWxpbmUgcG9pbnRzPSI3IDEwIDEyIDE1IDE3IDEwIi8+PGxpbmUgeDE9IjEyIiB5MT0iMTUiIHgyPSIxMiIgeTI9IjMiLz48L3N2Zz4=)](https://github.com/shadowrock-io/sn-api-helper-mcp/releases/latest/download/sn-api-helper-mcp.mcpb)

Download the `.mcpb` file from the latest release and open it with Claude Desktop. The extension installs automatically — no Python or manual configuration required.

---

## Purpose & Capabilities

The SignNow API Helper MCP server is a Model Context Protocol server designed to assist AI agents with SignNow API integration. It provides contextual documentation, code examples, and integration guidance.

**Core Functions:**

- **API Documentation Access:** Query the SignNow API documentation for endpoints, parameters, and usage patterns.
- **Code Examples:** Retrieve sample code for common SignNow API operations.
- **Authentication Help:** Reference guides for OAuth2 flows, token management, and required headers.
- **Integration Guidance:** Prompt templates for planning signing workflows, debugging errors, and setting up auth.
- **Error Resolution:** Error code reference and debugging prompts for common API issues.

---

## Run from Source

Clone the repo and run the server locally. Supports three transports: **streamable-http** (default), **stdio**, and **sse**.

```bash
git clone https://github.com/shadowrock-io/sn-api-helper-mcp.git
cd sn-api-helper-mcp
uv sync --all-extras
```

```bash
uv run python -m sn_api_helper_mcp                          # streamable-http on :8000
uv run python -m sn_api_helper_mcp --transport stdio         # stdio for MCP clients
uv run python -m sn_api_helper_mcp --transport sse --port 9000
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

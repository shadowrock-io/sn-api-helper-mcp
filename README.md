# SignNow API Helper MCP

[![License](https://img.shields.io/github/license/shadowrock-io/sn-api-helper-mcp)](https://github.com/shadowrock-io/sn-api-helper-mcp/blob/main/LICENSE.md)

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
| `get_signnow_api_info` | Query SignNow API documentation with content-type filtering. Returns endpoint details, parameters, code examples, and error handling guidance. |

Tool annotations: `readOnlyHint=true`, `idempotentHint=true`, `destructiveHint=false`. Responses use structured output via `json_response`.

**Tool parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | Search query. Best patterns: `{HTTP_METHOD} {resource} {action}` for endpoints, `{feature} guide` for walkthroughs. |
| `max_results` | int (1-10) | 3 | Number of documentation sections to return. |
| `content_type` | string | `"all"` | Filter by content type: `api-spec`, `guide`, `integration`, or `all`. |

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

Argument autocompletion for tool queries, prompt parameters, and resource template arguments. Provides suggestions for common API queries (using HTTP-method patterns), supported languages, use cases, content types, and guide topics.

---

## Improvements over Upstream

This fork introduces significant architectural improvements over the [upstream signnow/sn-api-helper-mcp](https://github.com/signnow/sn-api-helper-mcp) repository:

### Response Size Optimization

The upstream server passes raw Elasticsearch responses directly to the agent, often returning 200-300KB of content per query — flooding the agent's context window with irrelevant documentation.

This fork implements a multi-stage optimization pipeline:

- **JSON parsing and hit extraction** — parses the raw ES response and extracts only the top-scoring hits (default 3, configurable 1-10)
- **Per-document content budgets** — each document is capped at 8,000 characters with section-aware truncation at markdown boundaries
- **Overall hard cap** — total response size capped at 30,000 characters (~7,500 tokens), preventing context window exhaustion
- **Result**: ~90-96% response size reduction (329KB → 15-25KB for typical queries)

### Content-Type Re-Ranking

The upstream ES index mixes API specs, feature guides, and third-party integration walkthroughs (Salesforce, NetSuite, QuickBooks) with no relevance distinction. A query like "OAuth2 authentication" would return Salesforce integration guides alongside the actual API spec.

This fork applies client-side re-ranking with path-based boost factors:

| Content Type | Path Prefix | Boost Factor |
|-------------|-------------|-------------|
| API Spec | `reference/` | 1.5x |
| Guide | `docs/sn/guides/` | 1.0x |
| Integration | `docs/integration/` | 0.3x |
| Other | — | 0.7x |
| Noise (changelog, MCP meta-doc) | specific paths | 0.1x |

**Content-type filter parameter** — agents can set `content_type` to `api-spec`, `guide`, or `integration` for targeted searches, eliminating cross-contamination entirely.

### Query-Aware Content Extraction

The upstream server returns full documents from the top of each file, which means endpoints near the bottom of large OpenAPI spec files get truncated before the agent sees them.

This fork implements query-aware extraction:

- **OpenAPI endpoint matching** — for JSON API specs, parses the OpenAPI structure and extracts the specific endpoint(s) matching the query by scoring path segments, HTTP methods, operation summaries, and descriptions. Only the relevant endpoint(s) are returned, formatted as clean markdown with parameters, request bodies, and response codes.
- **Markdown section reordering** — for guide documents, splits content at section headers, scores each section by keyword relevance to the query, and reorders so the most relevant section appears first (before truncation applies).
- **Result**: queries like "GET document download" now return the download endpoint directly instead of truncating before reaching it.

### Noise Suppression

Known high-keyword-density documents that match many queries but provide little value (changelog, MCP server self-documentation) are heavily penalized (0.1x boost) and typically fall below the 50% relevance threshold, eliminating them from results entirely.

### Structured Output

All tool responses use Pydantic models with `json_response=True`, providing agents with structured metadata:

```json
{
  "query": "POST embedded signing invite",
  "content": "## Source: `reference/invite.json`\n\n### `POST /document/{id}/invite`\n...",
  "result_count": 3,
  "total_available": 46,
  "sources": ["reference/invite.json", "docs/sn/guides/embedded-signing.md"],
  "source": "SignNow API Documentation"
}
```

Agents can see how many total results exist and which sources were used, enabling smarter follow-up queries.

### CI/CD and Packaging

- **MCPB Desktop Extension** — automated GitHub Actions workflow builds `.mcpb` packages on every tagged release, with version auto-injection from the git tag
- **Auto-generated release notes** — each release includes a changelog derived from commit history
- **MCP spec validation** — built-in compliance validator script for specification conformance testing

---

## Architecture

```
src/sn_api_helper_mcp/
  cli.py              # Typer CLI — serve command with transport selection
  server.py           # FastMCP server factory with json_response + stateless_http
  cache.py            # In-memory TTL cache (15-min TTL) for API responses
  response_formatter.py  # Query-aware formatting: OpenAPI extraction, section reordering, truncation
  completions.py      # Argument completion handler (queries, content_type, max_results)
  tools/
    get_skills_info.py  # Async tool with content-type re-ranking, Pydantic output, retries, caching
  resources/
    api_reference.py    # Static SignNow API reference resources
  prompts/
    integration.py      # Integration, auth, and error debugging prompt templates
```

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
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

### MCP Spec Validation

Run the built-in spec compliance validator:

```bash
PYTHONPATH=src uv run python scripts/validate_mcp_spec.py
```

This starts the server via stdio, sends JSON-RPC requests to validate compliance with the MCP specification, and generates a coverage report.

---

## License

MIT

"""Static and dynamic SignNow API reference resources."""

from __future__ import annotations

from typing import Any

_AUTH_REFERENCE = """\
# SignNow API Authentication

## OAuth2 Token Endpoint
- **URL**: `https://api.signnow.com/oauth2/token`
- **Sandbox**: `https://api-eval.signnow.com/oauth2/token`
- **Method**: POST
- **Content-Type**: `application/x-www-form-urlencoded`

## Authorization Code Grant
```
POST /oauth2/token
Authorization: Basic {base64(client_id:client_secret)}

grant_type=authorization_code
&code={authorization_code}
&scope=*
```

## Password Grant (for testing/development)
```
POST /oauth2/token
Authorization: Basic {base64(client_id:client_secret)}

grant_type=password
&username={email}
&password={password}
&scope=*
```

## Refresh Token
```
POST /oauth2/token
Authorization: Basic {base64(client_id:client_secret)}

grant_type=refresh_token
&refresh_token={refresh_token}
```

## Required Headers for All API Calls
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

## Token Response
```json
{
  "access_token": "...",
  "token_type": "bearer",
  "expires_in": 2592000,
  "refresh_token": "...",
  "scope": "*"
}
```
"""

_BASE_URLS_REFERENCE = """\
# SignNow API Base URLs

## Production
- **API**: `https://api.signnow.com`
- **Web App**: `https://app.signnow.com`

## Sandbox (Evaluation)
- **API**: `https://api-eval.signnow.com`
- **Web App**: `https://app-eval.signnow.com`

## API Versioning
- Current version: v2 (prefix endpoints with `/v2/` where applicable)
- Legacy v1 endpoints still available but deprecated
- Use v2 endpoints for all new integrations

## Common Endpoint Patterns
- Documents: `/document/{document_id}`
- Templates: `/template/{template_id}`
- Users: `/user`
- Invites: `/document/{document_id}/invite`
- Embedded signing: `/v2/documents/{document_id}/embedded-invites`
"""

_ERROR_CODES_REFERENCE = """\
# SignNow API Error Codes

## HTTP Status Codes
| Code | Meaning | Action |
|------|---------|--------|
| 200  | Success | — |
| 201  | Created | Resource created successfully |
| 204  | No Content | Successful deletion |
| 400  | Bad Request | Check request body/params |
| 401  | Unauthorized | Refresh or re-authenticate token |
| 403  | Forbidden | Check user permissions |
| 404  | Not Found | Verify resource ID exists |
| 422  | Unprocessable Entity | Validation error — check field values |
| 429  | Too Many Requests | Rate limited — back off and retry |
| 500  | Internal Server Error | Retry after delay; contact support if persistent |

## Common Error Response Format
```json
{
  "errors": [
    {
      "code": 65536,
      "message": "Document not found"
    }
  ]
}
```

## Frequent Error Scenarios
- **"Invalid token"** (401): Token expired. Use refresh_token to get a new access_token.
- **"Document not found"** (404): Document ID is wrong or belongs to another user.
- **"Invite already exists"** (422): Cancel existing invite before creating a new one.
"""

_RATE_LIMITS_REFERENCE = """\
# SignNow API Rate Limits

## Default Limits
- **Per-user**: 60 requests per minute
- **Per-application**: 300 requests per minute
- **Bulk operations**: Lower limits apply

## Rate Limit Headers
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1609459200
```

## Best Practices
- Implement exponential backoff on 429 responses
- Cache frequently-accessed resources (documents, templates)
- Use webhooks instead of polling for status changes
- Batch operations where API supports it
"""

_WEBHOOKS_REFERENCE = """\
# SignNow Webhooks

## Webhook Setup
- **Endpoint**: `POST /v2/events`
- **Method**: Subscribe to events per-user or per-document

## Event Types
| Event | Description |
|-------|-------------|
| `document.create` | Document created |
| `document.update` | Document modified |
| `document.delete` | Document deleted |
| `document.complete` | All signers completed |
| `invite.create` | Signing invite sent |
| `invite.update` | Invite status changed |
| `document_group.create` | Document group created |
| `document_group.invite` | Group invite sent |

## Webhook Payload Format
```json
{
  "event": "document.complete",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "document_id": "...",
    "user_id": "..."
  }
}
```

## Security
- Verify webhook signatures using the callback_url secret
- Use HTTPS endpoints only
- Respond with 200 within 10 seconds to avoid retries
"""

_STATIC_RESOURCES: dict[str, tuple[str, str, str]] = {
    "signnow://api/authentication": (
        "Authentication Guide",
        "OAuth2 authentication flows, token endpoints, and required headers",
        _AUTH_REFERENCE,
    ),
    "signnow://api/base-urls": (
        "Base URLs & Versioning",
        "Production and sandbox base URLs, API versioning, common endpoint patterns",
        _BASE_URLS_REFERENCE,
    ),
    "signnow://api/error-codes": (
        "Error Codes Reference",
        "HTTP status codes, error response format, and common error scenarios",
        _ERROR_CODES_REFERENCE,
    ),
    "signnow://api/rate-limits": (
        "Rate Limits",
        "Default rate limits, headers, and best practices",
        _RATE_LIMITS_REFERENCE,
    ),
    "signnow://api/webhooks": (
        "Webhooks Reference",
        "Event types, payload format, setup, and security",
        _WEBHOOKS_REFERENCE,
    ),
}


def bind(mcp: Any) -> None:
    """Register all static resources on the MCP server."""

    @mcp.resource(
        "signnow://api/authentication",
        name="Authentication Guide",
        description="OAuth2 authentication flows, token endpoints, and required headers",
        mime_type="text/markdown",
    )
    def auth_resource() -> str:
        return _AUTH_REFERENCE

    @mcp.resource(
        "signnow://api/base-urls",
        name="Base URLs & Versioning",
        description="Production and sandbox base URLs, API versioning, common endpoint patterns",
        mime_type="text/markdown",
    )
    def base_urls_resource() -> str:
        return _BASE_URLS_REFERENCE

    @mcp.resource(
        "signnow://api/error-codes",
        name="Error Codes Reference",
        description="HTTP status codes, error response format, and common error scenarios",
        mime_type="text/markdown",
    )
    def error_codes_resource() -> str:
        return _ERROR_CODES_REFERENCE

    @mcp.resource(
        "signnow://api/rate-limits",
        name="Rate Limits",
        description="Default rate limits, headers, and best practices",
        mime_type="text/markdown",
    )
    def rate_limits_resource() -> str:
        return _RATE_LIMITS_REFERENCE

    @mcp.resource(
        "signnow://api/webhooks",
        name="Webhooks Reference",
        description="Event types, payload format, setup, and security",
        mime_type="text/markdown",
    )
    def webhooks_resource() -> str:
        return _WEBHOOKS_REFERENCE

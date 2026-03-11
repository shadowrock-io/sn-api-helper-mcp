"""Reusable prompt templates for common SignNow integration tasks."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field


def bind(mcp: Any) -> None:
    @mcp.prompt(
        name="signnow_integration",
        description="Generate a complete integration plan for a SignNow use case.",
    )
    def signnow_integration(
        use_case: Annotated[
            str,
            Field(
                description=(
                    "The integration use case, e.g. 'embedded signing', "
                    "'bulk send', 'template management', 'document generation'"
                )
            ),
        ],
        language: Annotated[
            str,
            Field(description="Programming language, e.g. 'python', 'node', 'php', 'java'"),
        ] = "python",
    ) -> str:
        return (
            f"Create a step-by-step integration plan for implementing {use_case} "
            f"with the SignNow API using {language}. Include:\n"
            "1. Required authentication setup (OAuth2)\n"
            "2. API endpoints to call, in order\n"
            "3. Request/response examples for each step\n"
            "4. Error handling for common failure modes\n"
            "5. Production best practices (rate limits, webhooks, retries)\n\n"
            "Use the get_signnow_api_info tool and SignNow resources for reference."
        )

    @mcp.prompt(
        name="signnow_auth_setup",
        description="Step-by-step OAuth2 authentication setup for SignNow API.",
    )
    def signnow_auth_setup(
        language: Annotated[
            str,
            Field(description="Programming language, e.g. 'python', 'node', 'php'"),
        ] = "python",
        grant_type: Annotated[
            str,
            Field(description="OAuth2 grant type: 'authorization_code' or 'password'"),
        ] = "authorization_code",
    ) -> str:
        return (
            f"Set up SignNow OAuth2 authentication using the {grant_type} grant "
            f"in {language}. Include:\n"
            "1. Application registration and credential setup\n"
            "2. Token request implementation with code example\n"
            "3. Token refresh logic\n"
            "4. Secure credential storage\n"
            "5. Error handling for auth failures\n\n"
            "Reference the signnow://api/authentication resource for endpoint details."
        )

    @mcp.prompt(
        name="signnow_error_debug",
        description="Debug a SignNow API error given status code and response.",
    )
    def signnow_error_debug(
        status_code: Annotated[
            str,
            Field(description="HTTP status code received, e.g. '401', '422', '500'"),
        ],
        error_message: Annotated[
            str,
            Field(description="Error message or response body from the API"),
        ] = "",
        endpoint: Annotated[
            str,
            Field(description="The API endpoint that returned the error"),
        ] = "",
    ) -> str:
        context = f"Endpoint: {endpoint}\n" if endpoint else ""
        msg = f"Error message: {error_message}\n" if error_message else ""
        return (
            f"Debug this SignNow API error:\n"
            f"HTTP Status: {status_code}\n"
            f"{context}{msg}\n"
            "Provide:\n"
            "1. What this error means in the SignNow API context\n"
            "2. Most common causes for this specific error\n"
            "3. Step-by-step resolution\n"
            "4. How to prevent it in the future\n\n"
            "Reference the signnow://api/error-codes resource and use "
            "get_signnow_api_info for detailed endpoint documentation."
        )

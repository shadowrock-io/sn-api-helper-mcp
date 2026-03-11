#!/usr/bin/env python3
"""MCP Spec Validation & Coverage Audit.

Starts the server via stdio, sends JSON-RPC requests to validate compliance
with the MCP specification, and generates a coverage report.

Usage:
    python scripts/validate_mcp_spec.py [--report MCP_SPEC_COVERAGE.md]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationResult:
    passed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class SpecCoverage:
    implemented: list[str] = field(default_factory=list)
    unused: list[tuple[str, str]] = field(default_factory=list)


_REQUEST_ID = 0


def _next_id() -> int:
    global _REQUEST_ID
    _REQUEST_ID += 1
    return _REQUEST_ID


def _jsonrpc_request(method: str, params: dict | None = None) -> bytes:
    """Encode a JSON-RPC request as newline-delimited JSON."""
    msg: dict = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": method,
    }
    if params:
        msg["params"] = params
    return (json.dumps(msg) + "\n").encode()


def _jsonrpc_notification(method: str) -> bytes:
    """Encode a JSON-RPC notification as newline-delimited JSON."""
    msg = {
        "jsonrpc": "2.0",
        "method": method,
    }
    return (json.dumps(msg) + "\n").encode()


async def _read_response(reader: asyncio.StreamReader) -> dict:
    """Read a single newline-delimited JSON-RPC message from the stream."""
    line = await asyncio.wait_for(reader.readline(), timeout=15.0)
    if not line:
        raise EOFError("Server closed the connection")
    return json.loads(line.decode())


async def _drain_notifications(reader: asyncio.StreamReader) -> dict:
    """Read responses, skipping notifications until we get a result with an id."""
    while True:
        resp = await _read_response(reader)
        if "id" in resp:
            return resp


async def validate_server(python_path: str) -> tuple[ValidationResult, SpecCoverage]:
    """Run the validation suite against the MCP server."""
    result = ValidationResult()
    coverage = SpecCoverage()

    proc = await asyncio.create_subprocess_exec(
        python_path,
        "-m",
        "sn_api_helper_mcp",
        "--transport",
        "stdio",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": "src"},
    )

    assert proc.stdin is not None
    assert proc.stdout is not None

    try:
        # --- Step 1: Initialize ---
        proc.stdin.write(
            _jsonrpc_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-validator", "version": "1.0.0"},
                },
            )
        )
        await proc.stdin.drain()

        init_resp = await _drain_notifications(proc.stdout)
        init_result = init_resp.get("result", {})

        # Check protocol version
        pv = init_result.get("protocolVersion", "")
        if pv:
            result.passed.append(f"protocolVersion present: {pv}")
        else:
            result.errors.append("Missing protocolVersion in initialize response")

        # Check serverInfo
        server_info = init_result.get("serverInfo", {})
        if server_info.get("name"):
            result.passed.append(f"serverInfo.name: {server_info['name']}")
        else:
            result.errors.append("Missing serverInfo.name (REQUIRED)")

        if init_result.get("instructions"):
            result.passed.append("instructions field present")
        else:
            result.warnings.append("Missing instructions field (RECOMMENDED)")

        # Check capabilities
        caps = init_result.get("capabilities", {})

        all_spec_capabilities = {
            "tools": "Tool registration and execution",
            "resources": "Static/dynamic data resources",
            "prompts": "Reusable prompt templates",
            "logging": "Server-side logging",
            "completions": "Argument autocompletion",
            "sampling": "Server-initiated LLM requests",
            "elicitation": "Server-initiated user prompts",
            "tasks": "Long-running task management",
        }

        for cap_name, description in all_spec_capabilities.items():
            if cap_name in caps:
                coverage.implemented.append(cap_name)
            else:
                coverage.unused.append((cap_name, description))

        # Send initialized notification
        proc.stdin.write(_jsonrpc_notification("notifications/initialized"))
        await proc.stdin.drain()

        # --- Step 2: Validate Tools ---
        if "tools" in caps:
            proc.stdin.write(_jsonrpc_request("tools/list", {}))
            await proc.stdin.drain()

            tools_resp = await _drain_notifications(proc.stdout)
            tools = tools_resp.get("result", {}).get("tools", [])

            for tool in tools:
                name = tool.get("name", "unnamed")

                if tool.get("name") and tool.get("inputSchema"):
                    result.passed.append(f"Tool '{name}': name + inputSchema present (REQUIRED)")
                else:
                    result.errors.append(f"Tool '{name}': missing name or inputSchema (REQUIRED)")

                if tool.get("description"):
                    result.passed.append(f"Tool '{name}': description present")
                else:
                    result.warnings.append(f"Tool '{name}': missing description (RECOMMENDED)")

                if tool.get("annotations"):
                    result.passed.append(f"Tool '{name}': annotations present")
                    annot = tool["annotations"]
                    for hint in [
                        "readOnlyHint",
                        "destructiveHint",
                        "idempotentHint",
                        "openWorldHint",
                    ]:
                        if hint in annot:
                            result.passed.append(f"Tool '{name}': {hint}={annot[hint]}")
                else:
                    result.warnings.append(
                        f"Tool '{name}': missing annotations (RECOMMENDED for spec compliance)"
                    )

                if tool.get("outputSchema"):
                    result.passed.append(f"Tool '{name}': outputSchema present (structured output)")
                else:
                    result.warnings.append(
                        f"Tool '{name}': missing outputSchema (RECOMMENDED for structured output)"
                    )
        else:
            result.warnings.append("No tools capability declared")

        # --- Step 3: Validate Resources ---
        if "resources" in caps:
            proc.stdin.write(_jsonrpc_request("resources/list", {}))
            await proc.stdin.drain()

            res_resp = await _drain_notifications(proc.stdout)
            resources = res_resp.get("result", {}).get("resources", [])

            for res in resources:
                uri = res.get("uri", "unknown")
                if res.get("uri") and res.get("name"):
                    result.passed.append(f"Resource '{uri}': uri + name present (REQUIRED)")
                else:
                    result.errors.append(f"Resource '{uri}': missing uri or name (REQUIRED)")

                if res.get("description"):
                    result.passed.append(f"Resource '{uri}': description present")
                else:
                    result.warnings.append(f"Resource '{uri}': missing description (RECOMMENDED)")

                if res.get("mimeType"):
                    result.passed.append(f"Resource '{uri}': mimeType present")
                else:
                    result.warnings.append(f"Resource '{uri}': missing mimeType (RECOMMENDED)")
        else:
            result.warnings.append("No resources capability declared")

        # --- Step 4: Validate Prompts ---
        if "prompts" in caps:
            proc.stdin.write(_jsonrpc_request("prompts/list", {}))
            await proc.stdin.drain()

            prompts_resp = await _drain_notifications(proc.stdout)
            prompts = prompts_resp.get("result", {}).get("prompts", [])

            for prompt in prompts:
                name = prompt.get("name", "unnamed")
                if prompt.get("name"):
                    result.passed.append(f"Prompt '{name}': name present (REQUIRED)")
                else:
                    result.errors.append(f"Prompt '{name}': missing name (REQUIRED)")

                if prompt.get("description"):
                    result.passed.append(f"Prompt '{name}': description present")
                else:
                    result.warnings.append(f"Prompt '{name}': missing description (RECOMMENDED)")
        else:
            result.warnings.append("No prompts capability declared")

    except asyncio.TimeoutError:
        result.errors.append("Timeout waiting for server response")
    except Exception as exc:
        result.errors.append(f"Unexpected error: {exc}")
    finally:
        proc.terminate()
        await proc.wait()

    return result, coverage


def generate_report(result: ValidationResult, coverage: SpecCoverage) -> str:
    """Generate a markdown spec coverage report."""
    lines = [
        "# MCP Spec Compliance & Coverage Report",
        "",
        "Auto-generated by `scripts/validate_mcp_spec.py`.",
        "",
        "## Validation Summary",
        "",
        f"- **Passed**: {len(result.passed)}",
        f"- **Warnings**: {len(result.warnings)}",
        f"- **Errors**: {len(result.errors)}",
        "",
    ]

    if result.errors:
        lines.append("## Errors (MUST fix)")
        lines.append("")
        for e in result.errors:
            lines.append(f"- {e}")
        lines.append("")

    if result.warnings:
        lines.append("## Warnings (SHOULD fix)")
        lines.append("")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## Spec Coverage")
    lines.append("")

    if coverage.implemented:
        lines.append("### Implemented Capabilities")
        lines.append("")
        for cap in coverage.implemented:
            lines.append(f"- {cap}")
        lines.append("")

    if coverage.unused:
        lines.append("### Available but Unused (Future Roadmap)")
        lines.append("")
        for cap, desc in coverage.unused:
            lines.append(f"- **{cap}**: {desc}")
        lines.append("")

    if result.passed:
        lines.append("## Detailed Pass List")
        lines.append("")
        for p in result.passed:
            lines.append(f"- {p}")
        lines.append("")

    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="MCP Spec Validation")
    parser.add_argument(
        "--report",
        default="MCP_SPEC_COVERAGE.md",
        help="Output path for the coverage report",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter to use",
    )
    args = parser.parse_args()

    print("Starting MCP spec validation...")
    result, coverage = await validate_server(args.python)

    report = generate_report(result, coverage)
    Path(args.report).write_text(report)
    print(f"Report written to {args.report}")

    # Print summary
    print(f"\nPassed: {len(result.passed)}")
    print(f"Warnings: {len(result.warnings)}")
    print(f"Errors: {len(result.errors)}")

    if result.errors:
        print("\nERRORS:")
        for e in result.errors:
            print(f"  - {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""Prompt registration for SignNow integration patterns."""

from __future__ import annotations

from typing import Any

from . import integration


def register_prompts(mcp: Any) -> None:
    integration.bind(mcp)

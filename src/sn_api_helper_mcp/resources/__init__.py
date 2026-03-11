"""Resource registration for SignNow API reference data."""

from __future__ import annotations

from typing import Any

from . import api_reference


def register_resources(mcp: Any) -> None:
    api_reference.bind(mcp)

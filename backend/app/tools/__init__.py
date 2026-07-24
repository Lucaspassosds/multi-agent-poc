"""Tools (function calling) — the public surface for the registry.

Re-exports so call sites import `from app.tools import ...` rather than reaching
into `app.tools.registry`. See registry.py for the specs + dispatcher.
"""
from app.tools.registry import TOOL_SPECS, dispatch  # noqa: F401

__all__ = ["TOOL_SPECS", "dispatch"]

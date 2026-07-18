"""MCP client — connect to the MCP server, list its tools, and call them.

This is provider-agnostic: we convert MCP tool definitions into our neutral ToolSpec
(spec 03) and expose a dispatch that calls them over the protocol. The same agent loop
(spec 04) then runs against MCP tools instead of in-process functions — proving the
"write once, reuse anywhere" claim (works on Gemini now, Claude later).
"""
import json
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import settings
from app.llm.base import ToolSpec


@asynccontextmanager
async def mcp_session():
    async with streamablehttp_client(settings.mcp_url) as (read, write, *_rest):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def list_tool_specs(session) -> list[ToolSpec]:
    listed = await session.list_tools()
    return [
        ToolSpec(
            name=t.name,
            description=t.description or "",
            parameters=t.inputSchema or {"type": "object", "properties": {}},
        )
        for t in listed.tools
    ]


def make_dispatch(session):
    """Return an async dispatch(name, args) -> JSON str that calls the tool over MCP."""
    async def dispatch(name: str, args: dict) -> str:
        try:
            result = await session.call_tool(name, arguments=args or {})
        except Exception as exc:
            return json.dumps({"error": repr(exc)})
        # MCP returns a list of content blocks; concatenate their text.
        texts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
        return "\n".join(texts) if texts else json.dumps({"result": "(no textual content)"})

    return dispatch

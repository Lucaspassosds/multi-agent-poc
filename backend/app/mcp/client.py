"""MCP client — connect to the MCP server, list its tools, and call them.

This is provider-agnostic: we convert MCP tool definitions into our neutral ToolSpec
(spec 03) and expose a dispatch that calls them over the protocol. The same agent loop
(spec 04) then runs against MCP tools instead of in-process functions — proving the
"write once, reuse anywhere" claim (works on Gemini now, Claude later).
"""
# ── Concept: MCP (CLIENT) ── converts MCP tool defs into our neutral ToolSpec + a dispatch that calls them over the protocol.
import json
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import settings
from app.llm.base import ToolSpec
from app.rag import search
from app.tools import registry


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


# ── Concept: MCP AS THE BACKBONE ── the orchestrator's hybrid retrieval runs THROUGH the
# protocol when the mcp service is up, and degrades to the in-process registry when it's down.
def _hits_to_rows(result_json: str) -> list[dict]:
    """MCP hybrid_search returns our HybridSearchResult as structured JSON; project its
    typed hits back to the row shape the retriever subagent already consumes."""
    data = json.loads(result_json)
    hits = data.get("hits", []) if isinstance(data, dict) else []
    return [{"id": h["chunk_id"], "document_id": h["document_id"],
             "source_type": h["source_type"], "title": h["title"],
             "content": h["preview"], "score": h["scores"]["fused"]}
            for h in hits]


@asynccontextmanager
async def mcp_search_or_local(search_mode: str):
    """Yield (search_fn, transport). For hybrid mode, probe the MCP server and — if up —
    run retrieval THROUGH the protocol (MCP is the backbone). If the mcp service is down,
    or the mode is lexical/semantic (eval-regression, not exposed over MCP), fall back to
    the in-process path. Capability negotiation (server name/proto/primitives) is logged."""
    if search_mode != "hybrid":
        # rag/search.py already exposes a SEARCH_FNS dispatch dict
        # ({"lexical": lexical_search, "semantic": semantic_search, "hybrid": hybrid_search})
        # as the single source of truth for mode dispatch — reuse it instead of inlining a
        # second dict here.
        async def local(subq: str, k: int):
            return await search.SEARCH_FNS[search_mode](subq, k)
        yield local, "in-process"
        return

    try:
        async with mcp_session() as session:
            init_tools = await session.list_tools()
            print(f"[mcp] backbone up: tools={[t.name for t in init_tools.tools]}")

            async def via_mcp(subq: str, k: int):
                res = await session.call_tool("hybrid_search", arguments={"query": subq, "k": k})
                texts = [c.text for c in res.content if getattr(c, "type", None) == "text"]
                return _hits_to_rows(texts[0]) if texts else []

            yield via_mcp, "mcp"
            return
    except Exception as exc:  # noqa: BLE001 - MCP down -> graceful in-process fallback
        print(f"[mcp] backbone unavailable ({exc!r}); falling back to in-process registry")

    async def fallback(subq: str, k: int):
        result = await registry.hybrid_search(query=subq, k=k)
        return _hits_to_rows(result.model_dump_json())
    yield fallback, "in-process"

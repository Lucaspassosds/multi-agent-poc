"""Standalone MCP server (topic: "MCP").

Exposes our search tools over the Model Context Protocol (Streamable HTTP) so ANY
MCP-aware client — our backend, Claude Desktop, an MCP inspector — can discover and
call them. Write the tool once, reuse anywhere.

Run as its own container: `python -m app.mcp_server` (see docker-compose `mcp` service).
Reuses the exact same search code as the in-process tools (single source of truth).
"""
# ── Concept: MCP (SERVER) ── the same search tools exposed over Model Context Protocol (Streamable HTTP :9000/mcp) for any MCP client.
from mcp.server.fastmcp import FastMCP

from app.tools import _get_document
from app.rag.search import hybrid_search as _hybrid

mcp = FastMCP("support-kb", host="0.0.0.0", port=9000)


@mcp.tool()
async def hybrid_search(query: str, k: int = 5) -> list[dict]:
    """Search the knowledge base and past resolved tickets for relevant passages."""
    rows = await _hybrid(query, k)
    return [
        {"chunk_id": r["id"], "document_id": r["document_id"], "source_type": r["source_type"],
         "title": r["title"], "preview": r["content"][:300]}
        for r in rows
    ]


@mcp.tool()
async def get_document(document_id: int) -> dict:
    """Fetch the full text of a knowledge-base document by its numeric id."""
    return await _get_document(document_id)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

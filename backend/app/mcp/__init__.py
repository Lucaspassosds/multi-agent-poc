"""MCP (Model Context Protocol) — server + client as one package.

server.py runs as its own container (`python -m app.mcp.server`, :9000/mcp);
client.py adapts MCP tools into the neutral ToolSpec/dispatch the agent loop uses.
"""

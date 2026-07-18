# 05 — MCP server + Skills (Phase 5)

## Purpose
Show two capability-extension mechanisms: **MCP** (a standard protocol so *any* MCP client can use our
tools) and **Skills** (packaged, on-demand expertise).

## MCP (topic: "MCP")

### 🎓 What problem it solves
Without MCP, every tool is hard-wired into one app. MCP is a standard wire protocol: a **server**
exposes tools/resources; any MCP-aware **client** (our agent, Claude Desktop, Cursor, …) can discover
and call them. Write the tool once, reuse everywhere.

### What we build
- **MCP server** (`mcp-server` Docker service) using the official Python `mcp` SDK (FastMCP), exposing:
  - `hybrid_search(query, k)` → same search as spec 02
  - `get_document(document_id)`
  - Transport: **Streamable HTTP** on the docker network.
- **Client side**: the backend uses the official `mcp` Python **client** to connect over HTTP, list the
  server's tools, and convert each into our **neutral tool spec** (spec 03). They flow into the same
  orchestrator loop from spec 04 — so MCP works on **any** provider (Gemini now, Claude later), not tied
  to the Anthropic SDK's MCP helpers.

### Why the local-client path (not the API MCP connector)
The API's `mcp_servers` connector has Anthropic connect to the server **server-side**, which needs a
publicly reachable URL. Our MCP server lives on the private docker network, so we use the **local MCP
client** helpers instead (backend → MCP server over the compose network). Documented so nobody wonders
why we didn't use the connector.

### Demo value
Point Claude Desktop (or `mcp` inspector) at the same server to show the tools working outside our app — proof of the "write once, reuse anywhere" claim.

### Acceptance
- [ ] MCP server starts; its tools are listable via the MCP inspector.
- [ ] The orchestrator answers a ticket using the MCP-provided `hybrid_search` (not the in-process one).

## Skills (topic: "skills")

### 🎓 Tools vs. Skills
A **tool** is a function call. A **skill** is packaged expertise — instructions (+ optional scripts/assets)
the model pulls in *on demand* when a task calls for it, without bloating the base prompt.

### What we build (POC-appropriate)
One **custom skill** — a `SKILL.md` "policy-reply-formatter": the house style, tone, mandatory
disclaimers, and citation format for support replies. The resolver invokes it when drafting the final
message. Progressive disclosure: only the skill's one-line description sits in context by default; the
full body loads when the resolver decides it's relevant.
- Implementation options: (a) a lightweight filesystem `SKILL.md` our orchestrator loads on demand —
  **provider-agnostic, works on Gemini now**; or (b) the Anthropic **Agent Skills** API
  (`container.skills` + code-execution + the `skills-2025-10-02` / `code-execution-2025-08-25` betas),
  which is **Claude-only → deferred until credits unblock**. We build **(a) now** to demo the Skills
  concept fully; (b) is the "productionized" Claude path we can add after the `LLM_PROVIDER=anthropic` swap.

### Acceptance
- [ ] A ticket reply is formatted by the skill (correct tone, disclaimer, citation format).
- [ ] With the skill removed, the reply is visibly less polished (shows the skill did work).

## Open questions
- Skill implementation (a) filesystem vs (b) Agent Skills API — confirm at build time; (a) recommended.
- Exact FastMCP transport/endpoint shape — verify against the running `mcp` package version in Phase 5.

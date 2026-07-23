# 03 — MCP Rework (all three primitives, made the backbone)

## Purpose
Turn MCP from a 2-tool side-demo into a textbook-complete server that exercises **all three MCP
primitives** and sits on the **critical retrieval path** — the single clearest signal of MCP fluency
to a reviewer, and a "connect Claude Desktop / Cursor to the same server" moment for a client.
Lands in `backend/app/mcp/` (see spec 01).

## Current state (why it reads as shallow / sloppy)
- `mcp_server.py` (~36 LoC) exposes **2** tools (`hybrid_search`, `get_document`) — only **1 of MCP's
  3 primitives** (tools). No resources, no prompts, no tool annotations, no structured output.
- Consumed on a **side path** `POST /agent/answer-mcp`; the real orchestrator uses in-process tools,
  so MCP isn't actually load-bearing.
- Declares 4 tools in the shared registry but exposes 2 — the gap flagged in spec 02.

## Contract — the reworked MCP server (`app/mcp/server.py`)
Built on the official Python `mcp` SDK (FastMCP), Streamable HTTP on the compose network (`:9000/mcp`).

### Primitive 1 — Tools (model-controlled actions)
Expose the **full** tool set from spec 05, each with:
- **Annotations**: `readOnlyHint` on `hybrid_search`/`get_document`/`get_ticket`/`lookup_customer`/
  `get_payment_status`/`check_refund_eligibility`; `destructiveHint: true` + `idempotentHint: false`
  on `escalate`.
- **Structured `outputSchema`**: typed results (from spec 05's Pydantic models), not `json.dumps` blobs.
- Annotations + schemas are the **single source of truth shared with the in-process registry** (spec 05),
  imported — never re-declared — so the "single source of truth" claim in the docstring becomes true.

### Primitive 2 — Resources (application-controlled context data, URI-addressed)
The primitive most POCs skip — highest-signal addition:
| URI | Returns |
|---|---|
| `kb://doc/{id}` | a KB document (markdown + metadata) |
| `kb://index` | browsable catalog of KB docs (id, title, source_type) |
| `ticket://{external_id}` | a seeded past ticket (precedent) |
| `skill://{name}` | a Skill's `SKILL.md` (ties MCP ↔ spec 04) |

Powers a "browse the KB over MCP" panel in the UI (spec 08).

### Primitive 3 — Prompts (user-controlled templates → slash commands)
- `/triage-refund` — structured template that seeds a refund-triage conversation.
- `/draft-reply` — draft a customer reply from a ticket + retrieved context.
- `/summarize-thread` — summarize a ticket thread.
Each declared with typed arguments; surfaces as slash commands in any MCP client.

### Making MCP the backbone
- Route the orchestrator's **retrieve** step through the `app/mcp/client.py` MCP client (list tools →
  neutral tool spec → same orchestrator loop), with the in-process registry as a **fallback** if the
  MCP service is down. So MCP is on the critical path, not a parallel demo.
- Preserve the documented reason for the **local-client path** over the API `mcp_servers` connector
  (server lives on the private docker network — connector needs a public URL). Keep that note.
- Display **capability negotiation** (server name, protocol version, primitives offered) and fire a
  `listChanged` notification on KB re-ingest.

## 🎓 Teaching note
MCP's value is **write-once-reuse-anywhere across an open protocol**. A server that only does tools is
half the story; resources (context) and prompts (reusable workflows) are what make it a real
integration surface. Pointing an external client (Claude Desktop / MCP inspector) at the same server
is the proof.

## Acceptance
- [ ] MCP inspector lists **tools (with annotations), resources, and prompts** — all three primitives.
- [ ] `kb://index` and `kb://doc/{id}` resolve; a resource is readable from an external MCP client.
- [ ] A prompt (`/triage-refund`) is invocable and returns a structured message template.
- [ ] The orchestrator resolves a real ticket using the **MCP-provided** `hybrid_search`, with a
      verified in-process fallback when the `mcp` service is stopped.
- [ ] Tool annotations + `outputSchema` are imported from the spec-05 registry (no duplicated declarations).

## Cross-refs & sequencing
- **Depends on spec 01 step 6** (files moved to `app/mcp/` + docker-compose command updated) — do the
  move first, land this rework in the new location.
- **Shares the tool contract with spec 05** — build spec 05's typed registry first (or in lockstep);
  this server imports it.
- **Provides resources consumed by spec 08** (KB-browse panel) and `skill://` from spec 04.

## Open questions
- Which transport exactly (Streamable HTTP vs SSE) — verify against the installed `mcp` package version.
- Should prompts live server-side only, or also seed the Triage UI's quick-actions? (Recommend both.)

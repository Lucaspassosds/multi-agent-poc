# Specs — Multi-Agent Support Triage POC

Spec-driven development: **we write the spec for a phase before we write its code.** Specs are the
source of truth; `tasks/todo.md` is the task tracker that points back here.

## Convention
- Each spec has: **Purpose**, **Contract** (interfaces/data shapes), **Behavior**, **Teaching notes** (🎓), **Open questions**.
- A spec is "done enough to build" when its Contract + Behavior are unambiguous.
- Later-phase specs (03–08) are written **just-in-time**, right before that phase, so they reflect what we learned building the earlier phases.

## Index (all specs written — ready for review)
| Spec | Phase | Status |
|---|---|---|
| `00-overview.md` — product, architecture, locked decisions, glossary | — | ✅ |
| `01-infrastructure.md` — docker-compose services | 0 | ✅ |
| `02-rag.md` — crawl → chunk → embed → store → hybrid search | 1 | ✅ |
| `03-claude-integration.md` — LLM provider abstraction (Gemini now / Claude later), retry, caching | 2 | ✅ |
| `04-agents.md` — tools, single agent, orchestrator, subagents, parallelism | 3–4 | ✅ |
| `05-mcp-and-skills.md` — MCP server + Skill | 5 | ✅ |
| `06-observability.md` — traces/spans + dashboard | 6 | ✅ |
| `07-evals.md` — golden set + metrics + LLM-as-judge | 7 | ✅ |
| `08-frontend.md` — React screens | 8 | ✅ |

Later specs may still get small revisions as we learn things building the earlier phases; any change
will be called out.

## Improvements track — `improvements/`
A second-round plan addressing reviewer feedback (findability, depth, client-facing polish). The
original `00-08` specs above stay as the source-of-truth for what was first built; the improvements
track layers on top. **Start at [`improvements/00-overview.md`](improvements/00-overview.md)** — it
holds the reframing, locked decisions, phased order of operations, and the scope-creep review.

| Spec | Scope |
|---|---|
| `improvements/00-overview.md` | Why, reframing, locked decisions, phasing, scope-creep review, success criteria |
| `improvements/01-restructure-discoverability.md` | Concept-first layout + `── Concept:` signposts + discoverability layer |
| `improvements/02-code-clarity.md` | Name-storm collapse, one-format concept tags, half-built-artifact fixes |
| `improvements/03-mcp-rework.md` | All three MCP primitives; MCP on the retrieval critical path |
| `improvements/04-skills-rework.md` | Skill library, 3-level disclosure, bundled executable script |
| `improvements/05-tools-rework.md` | Typed/annotated tools; gated real `escalate`; mock reads |
| `improvements/06-observability-langfuse.md` | Langfuse Cloud augmentation; scores; budgets; charts |
| `improvements/07-concept-depth.md` | Reranker, revise loop, chaos-toggle, eval taxonomy + gating |
| `improvements/08-frontend-polish.md` | Client/under-the-hood toggle; three-screen redesign |

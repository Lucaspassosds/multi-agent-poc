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

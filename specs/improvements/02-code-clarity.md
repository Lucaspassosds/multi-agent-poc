# 02 — Code Clarity (naming, signposts, readability)

## Purpose
Fix the manager's *"the code is sloppy/confusing"* complaint at the **line level**: kill the name
storms that make a concept impossible to grep, standardize the bilingual concept tags to one
greppable format, and remove the half-built artifacts that read as bugs. This spec is clarity only —
it does not add features and does not touch the MCP/Skills/Tools *behavior* (specs 03–05 rewrite
those; this spec's conventions are *applied inside* that rewrite, not before it).

> **Finding from the audit:** the backend is actually cleaner and more heavily commented than the
> "sloppy" verdict implied — nearly every module opens with a purpose docstring. The confusion is
> concentrated in a few high-traffic names and the concept tags. This spec targets those.

## Contract — the changes

### A. Collapse the name storms (highest "find-the-concept" ROI)
| Current (one concept, many names) | Proposed | Where |
|---|---|---|
| `hybrid_search` (rag) / `_hybrid` alias / `_hybrid_search` wrapper / ToolSpec `"hybrid_search"` / `@mcp.tool hybrid_search` — **5 names** | keep raw `hybrid_search`; drop the `_hybrid` alias; rename the wrapper `_run_hybrid_search_tool`; **or fold** per spec 05 | `rag/search.py`, `tools/registry.py`, `mcp/server.py` |
| `dispatch` / `_DISPATCH` / `make_dispatch` / inner `dispatch` / `dispatch_fn` — **4 meanings** | `run_tool` / `_TOOL_HANDLERS` / `make_mcp_tool_runner` / `run_tool_fn` | `tools/registry.py`, `mcp/client.py`, `agents/loop.py`, `api/agent.py` |
| `_get_document` imported across modules | make it public `get_document` | `mcp/server.py` imports `tools/registry.py` |

### B. Standardize concept tags → one greppable format (highest overall ROI)
Today tags are split **Portuguese** (`loop.py` "orquestração sem framework", `observability.py`
"observabilidade", `retry.py` "resolver retry", `orchestrator.py` "gestão de contexto") vs **English**
(`tools.py`, `skills.py`, `mcp_server.py`, `judge.py`, `metrics.py`), in two formats. Grepping the
English checklist names finds only half the concepts. **Convert all to the single banner form** from
spec 01 (`# ── Concept: <NAME> ──`), English, one per concept home. Placements (15):
`orchestrator.py`, `loop.py`, `mcp/client.py` *(currently untagged)*, `mcp/server.py`,
`tools/registry.py`, `skills/loader.py`, `rag/search.py` (+ "no external vector DB — pgvector only"),
`rag/ingest.py`, `observability.py`, `evals/metrics.py`, `evals/judge.py`, `llm/retry.py`,
`llm/base.py` (**prompt caching — currently has NO signpost anywhere**), `llm/factory.py` +
`llm/gemini.py`, and the parallelism gather in `orchestrator.py`.

### C. Fix the half-built artifacts that read as bugs
| Artifact | Problem | Fix (this spec, if not already replaced by 03–05) |
|---|---|---|
| MCP 2-vs-4 tool gap | server exposes 2 of 4 declared tools; system prompt still tells the model to call `escalate` | **superseded by spec 03** (all tools become real). Until then, one comment stating intent. |
| `list_skills()` dead code | never called; docstring sells an unused "list-then-load" protocol | **superseded by spec 04** (real model-driven selection). Until then, delete or annotate as deferred. |
| `"single source of truth"` docstring in `mcp_server.py` | contradicts a byte-identical copy of `_hybrid_search` | make it true by extracting one shared row→dict projection (spec 05 does this). |
| `cache_creation_tokens` | surfaced via API but never assigned (always 0) | one-line comment: "0 on Gemini; populated when the Anthropic provider reports it." |

### D. Readability quick-wins (mechanical, no behavior risk)
- Rename LLM-call helpers `_json`/`_text` → `_complete_json`/`_complete_text` (`orchestrator.py`).
- Rename `_accum` → `_add_usage`; anonymous `u1..u5` → `classify_usage … revise_usage`.
- Split semicolon-chained statements (`orchestrator.py:212,226,230,238`) — one statement per line.
- `rag/search.py`: `pool_n` → `candidate_pool_size`.
- `gemini.py`: extract `candidate = _first_candidate(resp)` once (currently pulled 2–3×).
- Add a one-line header to each of the two waterfall tree-walkers in `frontend/src/lib/waterfall.ts`
  ("live SSE" vs "restored ticket").

### E. Deeper (test-guarded) cleanups
- Centralize the duplicated search-mode map `{lexical,semantic,hybrid}` (`main.py` + `orchestrator.py`)
  into one `SEARCH_FNS`.
- Extract the duplicated `_dt` helper (`observability.py` + `evals/runner.py`).
- (Frontend) group the 7 `useState`/3 `useRef` in `TriagePage.tsx` into cohesive state objects — but
  spec 07 rewrites this screen, so **defer to spec 07**.

## 🎓 Teaching note
A concept a reviewer cannot `grep` is, to them, a concept that isn't there. One canonical name per
concept + one banner format converts the codebase into something you can *navigate by search* — which
is exactly how a reviewer (or a future you) reads unfamiliar code.

## Acceptance
- [ ] `grep -rn "hybrid_search\|dispatch" backend/app` returns only intentional, distinct meanings — no accidental near-duplicates.
- [ ] `grep -rn "── Concept:" backend/app` lists all 13 concepts in English, one format.
- [ ] No Portuguese concept tags remain in code (docs may keep the manager's original terms as aliases).
- [ ] No dead `list_skills()`/`_hybrid` alias left un-annotated (or removed by 03–05).
- [ ] `pytest`/existing verification green after the test-guarded cleanups (§E).

## Open questions
- Keep the manager's Portuguese concept terms anywhere? Recommend: only in `docs/CONCEPTS.md` as a
  parenthetical alias per row, so his mental vocabulary still maps, but code is monolingual English.

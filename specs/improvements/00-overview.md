# 00 — Improvements Overview

## Why this track exists
The engineering manager who commissioned this POC reviewed it and raised three concerns:
1. **Hard to find each concept in the code** — folder structure and file names were confusing, which
   made presenting difficult.
2. **Scope too small** to sufficiently explore each required concept in depth.
3. **From a client's perspective, it doesn't present pleasantly.**

He originally asked the project to explore: orchestration without a framework · MCP · RAG ·
observability · evals · skills · tools · lexical + semantic search in Postgres/pgvector (no other
vector DB) · using the Claude/Gemini API · context management via subagents · retry · parallelism ·
prompt caching.

This `specs/improvements/` track is the plan to address all three concerns. The original `specs/00-08`
remain untouched as the historical source-of-truth for what was first built.

## The reframing (what the analysis found)
Three independent reviewers (clean-code, structure, product) plus Langfuse research converged on one
picture: **the concepts are all present and the code is better-commented than "sloppy" implies — the
real problem is discoverability, a few high-traffic naming collisions, and shallow depth in exactly the
three modules the manager flagged: MCP, Skills, Tools.** So the three complaints map to three
composable workstreams, not three competing rewrites:

| Complaint | Workstream | Specs |
|---|---|---|
| Can't find the concepts | Structure + discoverability, code clarity | 01, 02 |
| Scope too small | Depth — headlined by the MCP/Skills/Tools rework | 03, 04, 05, 06, 07 |
| Not client-pleasing | Frontend polish + dual-audience toggle | 08 |

## Spec index
| Spec | Scope |
|---|---|
| `01-restructure-discoverability.md` | Concept-first layout; concept→home map; `── Concept:` signposts; `app/README.md`; blast-radius (HTTP/DB/frontend untouched) |
| `02-code-clarity.md` | Collapse `hybrid_search`/`dispatch` name storms; standardize bilingual tags → one English format; fix half-built artifacts |
| `03-mcp-rework.md` | All 3 MCP primitives (tools+annotations, resources, prompts); MCP on the retrieval critical path |
| `04-skills-rework.md` | Skill library; 3-level progressive disclosure; bundled executable script; model-driven selection |
| `05-tools-rework.md` | Strict schemas, typed outputs, annotations; gated real `escalate`; mock Stripe-like reads; single source of truth |
| `06-observability-langfuse.md` | Augment with **Langfuse Cloud**; provider-agnostic instrumentation; scores; budgets/percentiles; charts + deep-links |
| `07-concept-depth.md` | Bounded revise loop; RAG reranker + fusion transparency; retry chaos-toggle; context ledger; caching-correctness; eval taxonomy + regression gating |
| `08-frontend-polish.md` | Client/under-the-hood toggle; Triage hero; Run Inspector; Quality Dashboard |

## Locked decisions (from stakeholder review)
- **Structure:** concept-first & pragmatic — real modules get a folder; cross-cutting techniques
  (parallelism, caching, retry, subagent-context) get a named home + signpost, **not** an artificial folder.
- **Depth:** deepen within the **Stripe payments domain**; **do NOT add new agents** to the graph —
  improve the existing ones; **completely rework MCP / Skills / Tools** (the sloppiest triangle).
- **Audience:** serve **both** a polished client surface and an accessible technical view (one toggle).
- **Observability:** integrate **Langfuse — Cloud free tier**, **augmenting** (not replacing) the live
  SSE timeline + in-app waterfall. Provider-agnostic instrumentation preserves the Gemini→Claude swap.
- **Thesis preserved:** "framework-free" still holds — Langfuse is telemetry tooling, not an agent framework.

## Order of operations (and the one rule that prevents wasted work)
Phased so the app stays runnable (`docker compose up` + `/health`) after every step:

- **Phase A — Structure + discoverability (spec 01).** Foundational, near-zero risk. Do the file
  *moves* first so everything else lands in the right place.
- **Phase B — Clarity on the non-reworked modules (spec 02).** Signposts + name fixes everywhere
  *except* MCP/Skills/Tools.
- **Phase C — MCP / Skills / Tools rework (specs 05 → 03 → 04).** Build the typed tool registry (05)
  first; the MCP server (03) imports it; Skills (04) ties in via the eligibility script.
- **Phase D — Depth + observability (specs 07, 06).** Reranker, revise loop, chaos-toggle, eval
  taxonomy; wire Langfuse and push scores.
- **Phase E — Frontend polish (spec 08).** Last; depends on all backend capabilities above.

> **⚠ The rule:** do **not** apply spec 02's line-level cleanups to the MCP/Skills/Tools code, because
> specs 03–05 *replace* that code. Move it (Phase A), then rewrite it clean in place (Phase C). Spec 02's
> clarity conventions are *applied inside* the rework, not before it. This is the single cross-spec
> decision that avoids polishing code that's about to be deleted.

## Scope-creep review (requested: "spec everything, but review scope creep")
All 17 PO items are specced. This is the honest risk read and the **recommended cut-line** if time is
tight — everything below the line stays specced as a documented backlog.

**Must-do core (answers all three complaints directly — do these first):**
1. Structure + discoverability (01) · 2. Code clarity (02) · 3. MCP 3-primitive rework (03) ·
4. Skills library + bundled script (04) · 5. Tools schemas/annotations/gated escalate (05) ·
6. Langfuse augmentation + budgets (06) · 7. RAG reranker + eval taxonomy/gating + retry chaos-toggle (07) ·
8. Three-screen polish + toggle (08).

**Backlog (high value, but cut first under time pressure):**
| Item | Spec | Why it can wait |
|---|---|---|
| Provider A/B compare (Gemini vs Claude) | 07 | **Blocked** on the Claude/paid swap |
| Real prompt-cache numbers | 07 | **Blocked** on Claude; keep the honest free-tier disclosure now |
| Langfuse prompt-management registry | 06 | Nice demo, adds a network fetch per prompt; adopt only if time allows |
| Query decomposition / HyDE + wider fan-out | 07 | Reranker is the bigger RAG win; do it first |
| Context ledger | 07 | Great story, but instrumentation-heavy for a KPI |
| Char-offset citation grounding | 07 | Clickable chips can ship against `kb://doc/{id}` without exact offsets first |
| 3rd RAG source type | 07 | KB is already sufficient to demo hybrid search |
| Run-compare diff view | 06/08 | Lower impact than the KPI cards + Langfuse charts |

**Scope-creep guardrails (hold these or the POC balloons):**
- Mock `lookup_customer`/`get_payment_status` = **seeded fixtures only** — no real Stripe integration.
- Reranker = LLM-rerank or a small cross-encoder — **not** a training pipeline.
- **No new orchestration agents** — the revise loop lives *inside* the existing critique node.
- Langfuse = **Cloud free tier**, no self-hosted ClickHouse stack.
- Skills = 3–4 skills with **one** bundled script; MCP prompts/resources = a handful each — demonstrate
  the primitive, not exhaustiveness.

## Success criteria (mapped to the three complaints)
- **Findability:** `grep -rn "── Concept:" backend/app` lists all 13 concepts; every top-level folder
  maps to a concept in `backend/app/README.md`; a reviewer locates any concept in < 10s.
- **Depth:** MCP shows all 3 primitives; Skills runs a bundled script; Tools has a gated real
  `escalate`; RAG reranks; evals gate regressions; observability shows real Langfuse dashboards.
- **Presentation:** the client/under-the-hood toggle gives a clean product demo and a legible technical
  view from the same screens; the live timeline still sells the "watch it run" moment.

## Next step
Each spec is sized to become its own implementation plan. On approval, turn the must-do-core specs into
plans (writing-plans), in the Phase A→E order above.

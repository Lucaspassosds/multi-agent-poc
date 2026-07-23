# Phase B — Code Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the manager's *"the code is sloppy/confusing"* complaint at the line level, on every module **except** the MCP/Skills/Tools bodies (which Phase C rewrites): standardize the bilingual concept tags to one greppable English banner, kill the anonymous name storms that block grep-navigation, add the missing prompt-caching signpost, and remove the half-built artifacts that read as bugs — all with zero behavior change.

**Architecture:** Pure clarity edits to the non-reworked backend modules. Concept homes get one uniform `# ── Concept: <NAME> ──` banner (spec 01 convention); the retrieval-mode dispatch map and the epoch→UTC helper are each collapsed to a single source of truth in their concept home (`rag/search.py`, `observability.py`); LLM-call helpers, usage accumulators, and the Gemini candidate extraction are renamed/extracted for readability. Nothing in `mcp/`, `tools/registry.py`, or `skills/loader.py` bodies is touched — those names are finalized inside the Phase C rework; where a Phase-C name leaks into a non-reworked caller (the `dispatch` storm), only the non-registry call site is fixed here and the registry-side rename is explicitly deferred.

**Tech Stack:** Python 3.12 + FastAPI + asyncpg (backend); React 18 + TypeScript + Vite (frontend, verify-only this phase). Docker Compose for run/verify.

## Global Constraints

- **Runs AFTER Phase A (spec 01).** Phase A has already performed the file *moves*; this plan references **post-move paths**: `backend/app/tools/registry.py`, `backend/app/skills/loader.py`, `backend/app/mcp/client.py`, `backend/app/mcp/server.py`, `backend/app/api/agent.py`, `backend/app/rag/embeddings.py`, `backend/app/rag/seed_data.py`. Files Phase A does **not** move (edited here at their existing paths): `agents/orchestrator.py`, `agents/loop.py`, all `llm/*`, all `evals/*`, `rag/search.py`, `rag/ingest.py`, `observability.py`, `main.py`. All edit anchors below avoid the import lines Phase A rewrites, so they remain valid post-move.
- **The one cross-spec rule (spec 00):** do **NOT** apply line-level cleanups to the MCP/Skills/Tools *bodies* — specs 03–05 replace that code in Phase C. This plan may standardize a **concept banner/docstring tag** inside those files only where Phase C keeps it, but touches none of their logic. Everything the spec 02 name-storm/half-built tables assign to `mcp/`, `tools/registry.py`, or `skills/loader.py` is listed in **§ Explicitly deferred** below, not implemented here.
- **No new behavior, no API/DB/schema changes.** Every rename is internal; every public HTTP contract (`/search`, `/agent/*`, `/traces`, `/evals`) returns byte-identical shapes. Verification proves this per task.
- **NO test framework — deliberate, documented convention.** No pytest/TDD. Verification is manual: `docker compose exec frontend npm run build` (typecheck, only for frontend edits), `docker compose up -d && curl -s localhost:8000/health`, curling the affected endpoint to prove no behavior change, and `grep` assertions. Each task ends with its verification block + expected output, then a commit.
- **Concept-banner convention (spec 01):** exactly one line per concept home —
  `# ── Concept: <NAME> ── <one-clause description>.` — English only, placed immediately after the module docstring (or, for the two in-body concepts in `orchestrator.py`, immediately above the code they name).
- **Run/verify commands:** stack is `docker compose up -d` (services: `db`, `embeddings`, `backend` on `127.0.0.1:8000`, `mcp` on `:9000`, `frontend` on `:5173`); backend has no `--reload`, so **Python edits require `docker compose restart backend`** (and `mcp` only if its file changed — it never does this phase) before curling. Golden set is 20 cases.

---

## File Structure

- `backend/app/agents/orchestrator.py` — ORCHESTRATION + PARALLELISM banners; strip PT phrase; `_json/_text→_complete_json/_complete_text`; `_accum→_add_usage`; `u1..u5`→named; split 3 semicolon lines; use shared `SEARCH_FNS` (Modify).
- `backend/app/agents/loop.py` — TOOL-USE LOOP banner (strip PT tag); `dispatch_fn→run_tool_fn` param (Modify).
- `backend/app/observability.py` — OBSERVABILITY banner (strip PT tag); `cache_creation_tokens` comment; `_dt→to_utc` public helper (Modify).
- `backend/app/llm/retry.py` — RETRY banner (strip PT tag) (Modify).
- `backend/app/llm/base.py` — PROMPT CACHING banner + signpost comment (Modify).
- `backend/app/llm/factory.py` — PROVIDER SWAP banner (Modify).
- `backend/app/llm/gemini.py` — extract `_first_candidate(resp)` (Modify).
- `backend/app/evals/metrics.py` — EVALS (metrics) banner (strip `topic:`) (Modify).
- `backend/app/evals/judge.py` — EVALS (judge) banner (strip `topic:`) (Modify).
- `backend/app/evals/runner.py` — drop local `_dt`, import `to_utc` (Modify).
- `backend/app/rag/search.py` — HYBRID SEARCH banner; `pool_n→candidate_pool_size`; add canonical `SEARCH_FNS` map (Modify).
- `backend/app/rag/ingest.py` — RAG INGEST banner (Modify).
- `backend/app/main.py` — use shared `SEARCH_FNS` in `/search` (Modify).
- `backend/app/api/agent.py` — `dispatch_fn=`→`run_tool_fn=` keyword at the `run_agent` call (Modify).

---

## Task 1: Standardize concept tags → one English banner (spec 02 §B)

Add the uniform banner to each concept home in the **non-reworked** modules and delete every bilingual `topic:`/Portuguese tag from those files. (MCP/Tools/Skills banners are placed by Phase C — see § Explicitly deferred.)

**Files:**
- Modify: `backend/app/agents/orchestrator.py`, `backend/app/agents/loop.py`, `backend/app/observability.py`, `backend/app/llm/retry.py`, `backend/app/llm/factory.py`, `backend/app/evals/metrics.py`, `backend/app/evals/judge.py`, `backend/app/rag/search.py`, `backend/app/rag/ingest.py`

**Interfaces:** none — comments/docstrings only. (`llm/base.py`'s PROMPT CACHING banner is intentionally placed in Task 2 with the caching signpost so `base.py` is edited once.)

- [ ] **Step 1: `orchestrator.py` — ORCHESTRATION banner + strip the one Portuguese phrase.**

Replace the docstring's Portuguese parenthetical (line ~7):
```python
  returns a COMPACT result — the orchestrator never accumulates a giant transcript (gestão de contexto).
```
with:
```python
  returns a COMPACT result — the orchestrator never accumulates a giant transcript (subagent context isolation).
```
Then add the banner immediately after the closing `"""` of the module docstring (before `import asyncio`):
```python
"""
# ── Concept: ORCHESTRATION (framework-free) ── classify∥plan → retrieve×N → resolve → critique → revise, hand-rolled with asyncio; subagents keep isolated context.
import asyncio
```
(The PARALLELISM banner is added in Task 3 alongside the gather it names, to keep that region's edits together.)

- [ ] **Step 2: `loop.py` — TOOL-USE LOOP banner, strip PT tag.**

Replace line 1:
```python
"""The hand-rolled tool-use loop (topic: "orquestração sem framework").
```
with:
```python
"""The hand-rolled tool-use loop.
```
Add the banner after the docstring's closing `"""` (before `from app.agents.tools import ...`):
```python
"""
# ── Concept: TOOL-USE LOOP (framework-free) ── call model → run requested tools → feed results back → repeat, no agent framework.
from app.tools.registry import TOOL_SPECS, dispatch
```
(Import path shown is the Phase-A post-move form; do not otherwise change it — `dispatch` is renamed in Phase C.)

- [ ] **Step 3: `observability.py` — OBSERVABILITY banner, strip PT tag.**

Replace line 1:
```python
"""Phase 6 — a minimal, framework-free span tracer (topic: "observabilidade").
```
with:
```python
"""Phase 6 — a minimal, framework-free span tracer.
```
Add after the docstring's closing `"""` (before `import contextvars`):
```python
"""
# ── Concept: OBSERVABILITY ── framework-free span tracer; contextvars link parent spans; one Postgres write per trace.
import contextvars
```

- [ ] **Step 4: `retry.py` — RETRY banner, strip PT tag.**

Replace line 1:
```python
"""Retry with exponential backoff + jitter (topic: "resolver retry").
```
with:
```python
"""Retry with exponential backoff + jitter.
```
Add after the docstring's closing `"""` (before `import asyncio`):
```python
"""
# ── Concept: RETRY ── exponential backoff + jitter; honors Gemini's RetryInfo delay; transient (retry) vs permanent (surface) split.
import asyncio
```

- [ ] **Step 5: `factory.py` — PROVIDER SWAP banner.**

The whole module is a one-line docstring + code. Insert the banner after the docstring:
```python
"""Provider factory — picks the implementation from LLM_PROVIDER (one place to swap)."""
# ── Concept: PROVIDER SWAP (Claude/Gemini API) ── LLM_PROVIDER selects the implementation; agent code speaks neutral llm/base types only.
from functools import lru_cache
```

- [ ] **Step 6: `evals/metrics.py` — EVALS (metrics) banner, strip `topic:`.**

Replace line 1:
```python
"""Deterministic evals metrics (topic: "evals") — cheap, objective, no model call involved.
```
with:
```python
"""Deterministic evals metrics — cheap, objective, no model call involved.
```
Add after the docstring's closing `"""`:
```python
"""
# ── Concept: EVALS (deterministic metrics) ── cheap, objective, model-free scores over each golden-set case.


def classification_match(case: dict, result: dict) -> tuple[bool, bool]:
```

- [ ] **Step 7: `evals/judge.py` — EVALS (judge) banner, strip `topic:`.**

Replace line 1:
```python
"""LLM-as-judge (topic: "evals") — scores what deterministic metrics can't: whether the reply is
```
with:
```python
"""LLM-as-judge — scores what deterministic metrics can't: whether the reply is
```
Add after the docstring's closing `"""` (before `import json`):
```python
"""
# ── Concept: EVALS (LLM-as-judge) ── one structured call scores faithfulness + helpfulness the metrics can't measure.
import json
```

- [ ] **Step 8: `rag/search.py` — HYBRID SEARCH banner (with the pgvector note).**

Add after the docstring's closing `"""` (before `import asyncio`):
```python
"""
# ── Concept: HYBRID SEARCH ── lexical + semantic fused with Reciprocal Rank Fusion; pgvector only, no external vector DB.
import asyncio
```

- [ ] **Step 9: `rag/ingest.py` — RAG INGEST banner.**

Add after the docstring's closing `"""` (before `import json`):
```python
"""
# ── Concept: RAG INGEST ── fetch|synthetic → chunk → embed → store the knowledge base (documents + chunks).
import json
```

- [ ] **Step 10: Verify — every banner present, English-only, no Portuguese left in code.**

```bash
docker compose restart backend && sleep 3 && curl -s localhost:8000/health
grep -rn "── Concept:" backend/app --include=*.py
grep -rniE 'orquestra|observabilidade|gest[aã]o|resolver retry|sem framework|topic: "orquestra|topic: "observabilidade|topic: "resolver' backend/app --include=*.py
```
Expected:
- `/health` → `{"status":"ok",...}` (banners are comments; import/runtime unaffected).
- The `── Concept:` grep lists the **9** banners added here (orchestrator ORCHESTRATION, loop, observability, retry, factory, metrics, judge, search, ingest). The 10th (base.py PROMPT CACHING) lands in Task 2; orchestrator's PARALLELISM lands in Task 3; the MCP/Tools/Skills banners land in Phase C.
- The Portuguese grep returns **nothing** (all four PT `topic:` tags and the `gestão de contexto` phrase are gone). `topic: "tools"`, `topic: "skills"`, `topic: "MCP"` may still appear in the reworked files — that is expected and left for Phase C (they are English, so they do not violate the "no Portuguese" acceptance).

- [ ] **Step 11: Commit.**
```bash
git add backend/app/agents/orchestrator.py backend/app/agents/loop.py backend/app/observability.py backend/app/llm/retry.py backend/app/llm/factory.py backend/app/evals/metrics.py backend/app/evals/judge.py backend/app/rag/search.py backend/app/rag/ingest.py
git commit -m "refactor(clarity): standardize concept tags to one English banner

Replaces the bilingual/Portuguese \`topic:\` tags with the single
greppable \`# ── Concept: <NAME> ──\` banner form (spec 01) across the
non-reworked modules. MCP/Tools/Skills banners are placed inside the
Phase C rework, not here.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Prompt-caching signpost + `cache_creation_tokens` comment (spec 02 §C)

**Files:**
- Modify: `backend/app/llm/base.py`, `backend/app/observability.py`

**Interfaces:** none — one banner + two comments. No signature changes.

- [ ] **Step 1: `base.py` — PROMPT CACHING banner + explain the neutral `cache` flag.**

`llm/base.py` is the concept home for prompt caching (spec 02 §B notes it currently has **no signpost anywhere**). Add the banner after the module docstring (before `from __future__ import annotations`):
```python
"""
# ── Concept: PROMPT CACHING ── the neutral `cache` flag maps to Gemini's automatic implicit caching now and to Anthropic `cache_control` at the swap; savings normalize into Usage.cached_tokens.
from __future__ import annotations
```
The existing `Usage.cached_tokens` comment (`# normalized across providers ...`) and `LLMProvider.complete(..., cache: bool = True, ...)` already document the two ends; the banner ties them to the named concept. No further edit to `base.py`.

- [ ] **Step 2: `observability.py` — comment the always-zero `cache_creation_tokens` field.**

On the `SpanRecord` dataclass, annotate the field:
```python
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0  # 0 on Gemini; populated when the Anthropic provider reports cache-write tokens.
    retries: int = 0
```

- [ ] **Step 3: Verify.**
```bash
docker compose restart backend && sleep 3 && curl -s localhost:8000/health
grep -n "── Concept: PROMPT CACHING" backend/app/llm/base.py
grep -n "0 on Gemini" backend/app/observability.py
```
Expected: `/health` ok; both greps return their one line. Banner count is now 10 non-reworked concepts.

- [ ] **Step 4: Commit.**
```bash
git add backend/app/llm/base.py backend/app/observability.py
git commit -m "docs(clarity): add prompt-caching signpost and cache_creation_tokens note

llm/base.py gains the PROMPT CACHING concept banner (previously the one
concept with no signpost). observability.py documents why
cache_creation_tokens is always 0 on the Gemini free tier.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `orchestrator.py` readability quick-wins (spec 02 §D)

Rename the LLM-call helpers and usage accumulator, name the anonymous `u1..u5`, split the semicolon-chained statements, and add the PARALLELISM banner at the gather it names.

**Files:**
- Modify: `backend/app/agents/orchestrator.py`

**Interfaces:** all renamed names are **module-private** (`_json`, `_text`, `_accum`) — no other module imports them (verified: they are only referenced within `orchestrator.py`). No public signature changes.

- [ ] **Step 1: Rename the helper definitions.**

`_accum` → `_add_usage`:
```python
def _add_usage(total: dict, usage) -> None:
    total["input_tokens"] += usage.input_tokens
    total["output_tokens"] += usage.output_tokens
    total["cached_tokens"] += usage.cached_tokens
```
`_json` → `_complete_json` (keep body/comment identical):
```python
async def _complete_json(model, system, message, schema, max_tokens=1500):
    # thinking_budget=0: structured extraction needs no chain-of-thought, and leaving it on
    # can consume the whole output budget and truncate the JSON.
    resp = await get_provider().complete(
        model=model, system=system, messages=[user(message)], max_tokens=max_tokens,
        response_schema=schema, thinking_budget=0,
    )
    return json.loads(resp.text), resp.usage
```
`_text` → `_complete_text`:
```python
async def _complete_text(model, system, message, max_tokens=800):
    resp = await get_provider().complete(
        model=model, system=system, messages=[user(message)], max_tokens=max_tokens
    )
    return resp.text, resp.usage
```

- [ ] **Step 2: Update the helper call sites inside the subagents.**

Replace each `await _json(` with `await _complete_json(` (in `_classify`, `_plan`, `_critique`) and each `await _text(` with `await _complete_text(` (in `_retrieve`, `_resolve`). There are 3 `_json` calls and 2 `_text` calls; a mechanical rename:
```bash
# guidance only — verify by eye after:
# _json( → _complete_json(   ×3   |   _text( → _complete_text(   ×2
```

- [ ] **Step 3: Name the anonymous per-step usage vars in the nested emit helpers.**

In `_classify_emit`, `_plan_emit`, `_retrieve_emit`, rename the local `u` → `step_usage` (avoids shadowing the outer `usage` dict and kills the single-letter name):
```python
    async def _classify_emit():
        await emit({"type": "step_start", "step": "classify"})
        result, step_usage = await _classify(ticket)
        await emit({"type": "step_done", "step": "classify", "data": result})
        return result, step_usage

    async def _plan_emit():
        await emit({"type": "step_start", "step": "plan"})
        result, step_usage = await _plan(ticket)
        await emit({"type": "step_done", "step": "plan", "data": result})
        return result, step_usage

    async def _retrieve_emit(index: int, subquestion: str):
        await emit({"type": "step_start", "step": "retrieve", "index": index, "subquestion": subquestion})
        result, step_usage = await _retrieve(subquestion, search_mode)
        await emit({"type": "step_done", "step": "retrieve", "index": index, "data": result})
        return result, step_usage
```

- [ ] **Step 4: Name `u1..u5`, split the 3 semicolon lines, add the PARALLELISM banner.**

Replace the classify∥plan block (the PT-free version from Task 1 Step 1 is the anchor):
```python
        # 1) classify + plan concurrently (independent)
        (classification, u1), (subqs, u2) = await asyncio.gather(_classify_emit(), _plan_emit())
        _accum(usage, u1); _accum(usage, u2)
        questions = subqs["questions"][:max_subquestions]
```
with:
```python
        # 1) classify + plan concurrently (independent)
        (classification, classify_usage), (subqs, plan_usage) = await asyncio.gather(_classify_emit(), _plan_emit())
        _add_usage(usage, classify_usage)
        _add_usage(usage, plan_usage)
        questions = subqs["questions"][:max_subquestions]
```
Replace the retriever block:
```python
        # 2) retrievers in parallel — measure parallel vs would-be-sequential wall-clock
        t0 = time.time()
        retrieved = await asyncio.gather(*[_retrieve_emit(i, q) for i, q in enumerate(questions)])
        parallel_seconds = round(time.time() - t0, 2)
        evidences = [r for r, _ in retrieved]
        for _, u in retrieved:
            _accum(usage, u)
        sequential_estimate = round(sum(e["seconds"] for e in evidences), 2)
```
with (adds the PARALLELISM banner spec 02 §B places at the gather):
```python
        # 2) retrievers in parallel — measure parallel vs would-be-sequential wall-clock
        # ── Concept: PARALLELISM ── fan out the retriever subagents with asyncio.gather; the speedup is provable on overlapping span timestamps.
        t0 = time.time()
        retrieved = await asyncio.gather(*[_retrieve_emit(i, q) for i, q in enumerate(questions)])
        parallel_seconds = round(time.time() - t0, 2)
        evidences = [r for r, _ in retrieved]
        for _, retrieve_usage in retrieved:
            _add_usage(usage, retrieve_usage)
        sequential_estimate = round(sum(e["seconds"] for e in evidences), 2)
```
Replace the resolve line (split the semicolon):
```python
        draft, u3 = await _resolve(ticket, classification, evidences, skill_body=skill_body); _accum(usage, u3)
```
with:
```python
        draft, draft_usage = await _resolve(ticket, classification, evidences, skill_body=skill_body)
        _add_usage(usage, draft_usage)
```
Replace the critique line (split the semicolon):
```python
        critique, u4 = await _critique(ticket, draft, evidences); _accum(usage, u4)
```
with:
```python
        critique, critique_usage = await _critique(ticket, draft, evidences)
        _add_usage(usage, critique_usage)
```
Replace the revision block:
```python
            revised, u5 = await _resolve(ticket, classification, evidences,
                                         fixes=critique.get("fixes"), skill_body=skill_body)
            _accum(usage, u5)
```
with:
```python
            revised, revise_usage = await _resolve(ticket, classification, evidences,
                                                   fixes=critique.get("fixes"), skill_body=skill_body)
            _add_usage(usage, revise_usage)
```

- [ ] **Step 5: Verify — no old names left; behavior unchanged on a live triage.**
```bash
docker compose restart backend && sleep 3 && curl -s localhost:8000/health
grep -nE '\b_json\b|\b_text\b|\b_accum\b|\bu[1-5]\b|; _' backend/app/agents/orchestrator.py || echo "OK: no old names / semicolons"
curl -s -X POST localhost:8000/agent/triage \
  -H 'content-type: application/json' \
  -d '{"message":"My refund from last week still has not arrived."}' \
  | python3 -c 'import sys,json;r=json.load(sys.stdin);print("keys ok:",all(k in r for k in ("classification","evidence","final_reply","usage","parallelism","trace_id")));print("usage:",r["usage"])'
```
Expected: `/health` ok; the grep prints `OK: no old names / semicolons`; the triage returns the full result shape (`keys ok: True`) with a populated `usage` dict whose totals are non-zero — proving `_add_usage` still accumulates across all five steps exactly as before.

- [ ] **Step 6: Commit.**
```bash
git add backend/app/agents/orchestrator.py
git commit -m "refactor(orchestrator): readable helper/usage names, one statement per line

_json/_text→_complete_json/_complete_text, _accum→_add_usage, anonymous
u1..u5→named per-step usages, split the three semicolon-chained lines,
and add the PARALLELISM concept banner at the retriever gather. No
behavior change — same result shape and usage totals.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `rag/search.py` — `pool_n` → `candidate_pool_size` (spec 02 §D)

**Files:**
- Modify: `backend/app/rag/search.py`

**Interfaces:** `pool_n` is a keyword-only-in-practice parameter of `hybrid_search`; no caller passes it (verified — `main.py`, `orchestrator.py`, and the reworked `tools`/`mcp` callers all call `hybrid_search(query, k)` positionally). Renaming is safe and internal.

- [ ] **Step 1: Rename the parameter and its two uses.**

Replace:
```python
async def hybrid_search(query: str, k: int = 10, rrf_k: int = 60, pool_n: int = 20) -> list[dict]:
    # Run both retrievals concurrently — a first taste of the parallelism theme.
    lex, sem = await asyncio.gather(
        lexical_search(query, pool_n),
        semantic_search(query, pool_n),
    )
```
with:
```python
async def hybrid_search(query: str, k: int = 10, rrf_k: int = 60, candidate_pool_size: int = 20) -> list[dict]:
    # Pull a wider candidate pool from each retriever, then fuse down to k — RRF needs depth to rank.
    # Run both retrievals concurrently — a first taste of the parallelism theme.
    lex, sem = await asyncio.gather(
        lexical_search(query, candidate_pool_size),
        semantic_search(query, candidate_pool_size),
    )
```

- [ ] **Step 2: Verify — name gone; hybrid search still returns fused, ranked rows.**
```bash
docker compose restart backend && sleep 3 && curl -s localhost:8000/health
grep -n 'pool_n' backend/app/rag/search.py || echo "OK: pool_n gone"
curl -s 'localhost:8000/search?q=refund%20not%20received&mode=hybrid&k=5' \
  | python3 -c 'import sys,json;r=json.load(sys.stdin);print("mode:",r["mode"],"n:",len(r["results"]),"scored:",all("score" in x for x in r["results"]))'
```
Expected: `/health` ok; `OK: pool_n gone`; `mode: hybrid n: 5 scored: True`.

- [ ] **Step 3: Commit.**
```bash
git add backend/app/rag/search.py
git commit -m "refactor(rag): pool_n → candidate_pool_size in hybrid_search

Names the wider pre-fusion candidate pool RRF ranks over. Internal
parameter, no caller passed it; search results unchanged.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `gemini.py` — extract `_first_candidate` once (spec 02 §D)

The response's first candidate is pulled 3× with the same guard (`_extract_text` line ~62, `_to_response` `cand0` line ~74 and `cand` line ~89). Extract one helper and reuse it.

**Files:**
- Modify: `backend/app/llm/gemini.py`

**Interfaces:** `_first_candidate` is a new module-private helper; no external surface changes. Behavior is identical (same guard, same `[0]`).

- [ ] **Step 1: Add the helper above `_extract_text`.**

Insert before `def _extract_text(resp) -> str:`:
```python
def _first_candidate(resp):
    # Gemini responses carry a candidates list; every reader wants candidates[0] with the same
    # None-safe guard. One helper so text-extraction and tool/finish parsing agree on "the candidate".
    return (getattr(resp, "candidates", None) or [None])[0]


```

- [ ] **Step 2: Use it in `_extract_text`.**

Replace:
```python
def _extract_text(resp) -> str:
    try:
        cand = (resp.candidates or [None])[0]
        if not cand or not cand.content or not cand.content.parts:
            return ""
        return "".join(p.text for p in cand.content.parts if getattr(p, "text", None))
    except Exception:
        return ""
```
with:
```python
def _extract_text(resp) -> str:
    try:
        cand = _first_candidate(resp)
        if not cand or not cand.content or not cand.content.parts:
            return ""
        return "".join(p.text for p in cand.content.parts if getattr(p, "text", None))
    except Exception:
        return ""
```

- [ ] **Step 3: Use it in `_to_response` (both pulls).**

Replace:
```python
    calls: list[ToolCall] = []
    cand0 = (getattr(resp, "candidates", None) or [None])[0]
    if cand0 and cand0.content and cand0.content.parts:
        for i, part in enumerate(cand0.content.parts):
```
with:
```python
    calls: list[ToolCall] = []
    cand = _first_candidate(resp)
    if cand and cand.content and cand.content.parts:
        for i, part in enumerate(cand.content.parts):
```
and replace the second pull:
```python
    cand = (getattr(resp, "candidates", None) or [None])[0]
    finish = str(getattr(cand, "finish_reason", None)) if cand else None
```
with:
```python
    finish = str(getattr(cand, "finish_reason", None)) if cand else None
```
(The `cand` from the first pull is now reused for `finish_reason`; the redundant re-pull is deleted.)

- [ ] **Step 4: Verify — single extraction point; provider still returns text + usage.**
```bash
docker compose restart backend && sleep 3 && curl -s localhost:8000/health
grep -cn 'or \[None\])\[0\]' backend/app/llm/gemini.py    # expect 1 (only inside _first_candidate)
curl -s -X POST localhost:8000/agent/answer \
  -H 'content-type: application/json' \
  -d '{"message":"How long do Stripe refunds take?"}' \
  | python3 -c 'import sys,json;r=json.load(sys.stdin);print("answer non-empty:",bool(r.get("answer")),"| usage:",r.get("usage"))'
```
Expected: `/health` ok; the grep prints `1` (the candidate access now exists only inside `_first_candidate`); the agent answer is non-empty with a populated `usage` — text extraction and tool parsing both still work.

- [ ] **Step 5: Commit.**
```bash
git add backend/app/llm/gemini.py
git commit -m "refactor(gemini): extract _first_candidate() to stop re-pulling candidates[0]

Text extraction, tool-call parsing, and finish_reason now share one
None-safe candidate accessor instead of three copies of the same guard.
No behavior change.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `dispatch` name-storm — fix the non-registry call sites only (spec 02 §A)

Spec 02 §A collapses `dispatch / _DISPATCH / make_dispatch / inner dispatch / dispatch_fn` → `run_tool / _TOOL_HANDLERS / make_mcp_tool_runner / run_tool_fn`. The registry-side (`tools/registry.py` `dispatch`→`run_tool`, `_DISPATCH`→`_TOOL_HANDLERS`) and MCP-side (`mcp/client.py` `make_dispatch`→`make_mcp_tool_runner`) renames are **finalized in Phase C** (they are inside the reworked bodies). Here we fix only the **non-registry** name: `run_agent`'s parameter `dispatch_fn`, which lives in the non-reworked `agents/loop.py`, and its single external caller.

**Files:**
- Modify: `backend/app/agents/loop.py`, `backend/app/api/agent.py`

**Interfaces:** `run_agent(..., dispatch_fn=...)` → `run_agent(..., run_tool_fn=...)`. Two call sites: `api/agent.py:answer_mcp` (keyword arg) and the default (the registry symbol, still named `dispatch` until Phase C). No behavior change.

- [ ] **Step 1: `loop.py` — rename the parameter and its body use.**

Replace:
```python
    tools: list[ToolSpec] = TOOL_SPECS,
    dispatch_fn=dispatch,
    max_iters: int = 6,
) -> dict:
    # dispatch_fn defaults to the in-process tools; the MCP path (spec 05) passes a
    # dispatch that calls tools over the protocol instead — same loop either way.
```
with:
```python
    tools: list[ToolSpec] = TOOL_SPECS,
    run_tool_fn=dispatch,
    max_iters: int = 6,
) -> dict:
    # run_tool_fn defaults to the in-process tool runner (`dispatch`, renamed to `run_tool` in
    # Phase C / spec 05); the MCP path passes a runner that calls tools over the protocol
    # instead — same loop either way.
```
Replace the body call:
```python
                async with span(f"tool:{call.name}", "tool"):
                    tool_output = await dispatch_fn(call.name, call.args)
```
with:
```python
                async with span(f"tool:{call.name}", "tool"):
                    tool_output = await run_tool_fn(call.name, call.args)
```

- [ ] **Step 2: `api/agent.py` — pass the renamed keyword.**

Replace (in `answer_mcp`):
```python
        result = await run_agent(
            system=_SYSTEM, message=body.message, model=settings.model_resolve,
            tools=tools, dispatch_fn=dispatch,
        )
```
with:
```python
        result = await run_agent(
            system=_SYSTEM, message=body.message, model=settings.model_resolve,
            tools=tools, run_tool_fn=dispatch,
        )
```
(The local `dispatch = make_dispatch(session)` and its `make_dispatch` import are the MCP-client symbol, renamed to `make_mcp_tool_runner` in Phase C — leave them here.)

- [ ] **Step 3: Verify — no `dispatch_fn` remains; both agent paths still run.**
```bash
docker compose restart backend && sleep 3 && curl -s localhost:8000/health
grep -rn 'dispatch_fn' backend/app --include=*.py || echo "OK: dispatch_fn gone"
# in-process tools path (uses the default run_tool_fn):
curl -s -X POST localhost:8000/agent/answer -H 'content-type: application/json' \
  -d '{"message":"Where is my refund?"}' | python3 -c 'import sys,json;print("answer path ok:",bool(json.load(sys.stdin).get("answer")))'
# MCP tools path (passes run_tool_fn explicitly) — needs the mcp service up:
curl -s -X POST localhost:8000/agent/answer-mcp -H 'content-type: application/json' \
  -d '{"message":"Where is my refund?"}' | python3 -c 'import sys,json;r=json.load(sys.stdin);print("mcp path ok:",bool(r.get("answer")),"| source:",r.get("tools_source"))'
```
Expected: `/health` ok; `OK: dispatch_fn gone`; `answer path ok: True`; `mcp path ok: True | source: mcp`. Both the default and the explicit runner still work — the rename is name-only.

- [ ] **Step 4: Commit.**
```bash
git add backend/app/agents/loop.py backend/app/api/agent.py
git commit -m "refactor(loop): run_agent dispatch_fn → run_tool_fn (non-registry site)

Renames the loop's tool-runner parameter and its one external caller.
The registry symbol it defaults to (\`dispatch\`) and the MCP factory
(\`make_dispatch\`) are renamed to run_tool / make_mcp_tool_runner in
Phase C, where those reworked bodies live.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Centralize the search-mode map into one `SEARCH_FNS` (spec 02 §E)

The `{lexical, semantic, hybrid}` dispatch map is duplicated in `orchestrator.py` (`_SEARCH_FNS`, lines ~30) and `main.py` (inline dict in `/search`, lines ~118). Collapse to one public map in its concept home, `rag/search.py`.

**Files:**
- Modify: `backend/app/rag/search.py`, `backend/app/agents/orchestrator.py`, `backend/app/main.py`

**Interfaces:** new `rag.search.SEARCH_FNS: dict[str, Callable]`. Both consumers already `import app.rag.search as search_mod`, so they reference `search_mod.SEARCH_FNS` — no new import lines.

- [ ] **Step 1: `rag/search.py` — add the canonical map at end of file.**

Append after `hybrid_search`:
```python


# The single source of truth for retrieval-mode dispatch, shared by the HTTP /search endpoint
# (main.py) and the retriever subagents (orchestrator.py). A new mode is added in exactly one
# place. Defaulting a retriever to "lexical"/"semantic" lets the Phase 7 evals demonstrate a
# deliberate regression (hybrid is strictly better) without duplicating the orchestrator flow.
SEARCH_FNS = {
    "lexical": lexical_search,
    "semantic": semantic_search,
    "hybrid": hybrid_search,
}
```

- [ ] **Step 2: `orchestrator.py` — delete the local `_SEARCH_FNS`, use the shared map.**

Delete the block (the PT phrase in it was already handled; this removes the whole dict + comment):
```python
# Retrieval mode dispatch — same dict-dispatch pattern as main.py's /search. Defaulting a
# retriever to "lexical" or "semantic" lets Phase 7 evals demonstrate a deliberate regression
# (hybrid is strictly better) without duplicating the orchestrator flow.
_SEARCH_FNS = {
    "lexical": search_mod.lexical_search,
    "semantic": search_mod.semantic_search,
    "hybrid": search_mod.hybrid_search,
}


```
Update the use in `_retrieve`:
```python
        rows = await _SEARCH_FNS[search_mode](subquestion, k=4)
```
→
```python
        rows = await search_mod.SEARCH_FNS[search_mode](subquestion, k=4)
```

- [ ] **Step 3: `main.py` — use the shared map in `/search`.**

Replace:
```python
    fn = {
        "lexical": search_mod.lexical_search,
        "semantic": search_mod.semantic_search,
        "hybrid": search_mod.hybrid_search,
    }[mode]
    rows = await fn(q, k)
```
with:
```python
    fn = search_mod.SEARCH_FNS[mode]
    rows = await fn(q, k)
```

- [ ] **Step 4: Verify — one definition, both consumers agree, all three modes work.**
```bash
docker compose restart backend && sleep 3 && curl -s localhost:8000/health
grep -rn 'SEARCH_FNS' backend/app --include=*.py    # expect: 1 definition in rag/search.py + 1 use each in orchestrator.py & main.py
grep -n '_SEARCH_FNS' backend/app/agents/orchestrator.py || echo "OK: local _SEARCH_FNS gone"
for m in lexical semantic hybrid; do
  curl -s "localhost:8000/search?q=refund&mode=$m&k=3" | python3 -c "import sys,json;r=json.load(sys.stdin);print('$m:',r['mode'],len(r['results']))"
done
```
Expected: `/health` ok; `SEARCH_FNS` appears exactly 3× (definition + 2 uses); `OK: local _SEARCH_FNS gone`; each mode returns 3 results with the right `mode` label — the map behaves identically from both entrypoints.

- [ ] **Step 5: Commit.**
```bash
git add backend/app/rag/search.py backend/app/agents/orchestrator.py backend/app/main.py
git commit -m "refactor(rag): single SEARCH_FNS dispatch map for /search and retrievers

Collapses the duplicated {lexical,semantic,hybrid} map (orchestrator's
_SEARCH_FNS + main.py's inline dict) into one canonical map in its
concept home, rag/search.py. A new mode is added in exactly one place.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Extract the duplicated `_dt` helper (spec 02 §E)

Identical `_dt(ts) -> datetime` appears in `observability.py` (line ~61) and `evals/runner.py` (line ~34). Promote the observability one to a public `to_utc` (its concept home owns trace/eval timestamp persistence) and have the eval runner import it.

**Files:**
- Modify: `backend/app/observability.py`, `backend/app/evals/runner.py`

**Interfaces:** `observability.to_utc(ts: float) -> datetime` becomes public. `evals/runner.py` already imports `cost_usd` from `app.observability` (no circular-import risk). No signature/behavior change.

- [ ] **Step 1: `observability.py` — rename `_dt` → `to_utc` and update its three uses.**

Replace the definition:
```python
def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)
```
with:
```python
def to_utc(ts: float) -> datetime:
    """Epoch seconds → aware UTC datetime. Shared with evals/runner.py so trace and eval-run
    rows are persisted with identical timestamp handling."""
    return datetime.fromtimestamp(ts, tz=timezone.utc)
```
Then update the three call sites in `_persist` (the `INSERT INTO traces` and `INSERT INTO spans` values):
```python
                self.name, self.ticket_id, _dt(self._root.started_at), _dt(self._root.ended_at),
```
→
```python
                self.name, self.ticket_id, to_utc(self._root.started_at), to_utc(self._root.ended_at),
```
and:
```python
                    _dt(s.started_at), _dt(s.ended_at or s.started_at),
```
→
```python
                    to_utc(s.started_at), to_utc(s.ended_at or s.started_at),
```

- [ ] **Step 2: `evals/runner.py` — import `to_utc`, delete the local `_dt`, update uses.**

Change the import:
```python
from app.observability import cost_usd
```
→
```python
from app.observability import cost_usd, to_utc
```
Delete the local helper:
```python
def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


```
Update its three uses (in `_persist`'s `eval_runs` insert and the `run_eval` return dict):
```python
            _dt(started), _dt(ended), retrieval_mode, aggregate["n_cases"],
```
→
```python
            to_utc(started), to_utc(ended), retrieval_mode, aggregate["n_cases"],
```
and:
```python
        "started_at": _dt(started).isoformat(),
        "ended_at": _dt(ended).isoformat(),
```
→
```python
        "started_at": to_utc(started).isoformat(),
        "ended_at": to_utc(ended).isoformat(),
```
Note: `runner.py` still imports `datetime, timezone` for its type-only use? After removing `_dt`, check whether `datetime`/`timezone` are still referenced — they are **not** (they were only used by `_dt`). Remove the now-unused import to keep the module clean:
```python
from datetime import datetime, timezone
```
→ (delete the line entirely).

- [ ] **Step 3: Verify — one `_dt`-style helper; traces and eval runs still persist.**
```bash
docker compose restart backend && sleep 3 && curl -s localhost:8000/health
grep -rn 'def _dt\|def to_utc' backend/app --include=*.py    # expect: exactly one def to_utc (observability.py)
grep -rn '\b_dt(' backend/app --include=*.py || echo "OK: no _dt calls left"
# trace persistence (any triage writes a trace with started/ended timestamps):
curl -s -X POST localhost:8000/agent/triage -H 'content-type: application/json' \
  -d '{"message":"My subscription was charged twice."}' >/dev/null
curl -s 'localhost:8000/traces?limit=1' | python3 -c 'import sys,json;r=json.load(sys.stdin);t=(r if isinstance(r,list) else r.get("traces",r))[0];print("trace persisted:",bool(t.get("started_at")) and bool(t.get("ended_at")))'
```
Expected: `/health` ok; exactly one `def to_utc` and no `def _dt`; `OK: no _dt calls left`; `trace persisted: True` (timestamps round-trip through `to_utc` unchanged). The eval-run path uses the same helper — a full `/evals/run` (20 cases, several minutes on the free tier) is optional; the shared code is proven by the trace write.

- [ ] **Step 4: Commit.**
```bash
git add backend/app/observability.py backend/app/evals/runner.py
git commit -m "refactor(observability): share one to_utc() instead of duplicated _dt

Promotes observability's private _dt to a public to_utc() and imports it
in evals/runner.py, removing the byte-identical copy (and its now-unused
datetime import). Timestamp persistence is unchanged.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Explicitly deferred (NOT done in Phase B — recorded so the spec-02 coverage is auditable)

Per spec 00's cross-spec rule, these spec-02 items live inside code Phase C/E replaces; doing them now would polish soon-deleted code:

| Spec 02 item | Where it lives | Deferred to |
|---|---|---|
| `hybrid_search` storm collapse: drop `_hybrid` alias, rename wrapper `_run_hybrid_search_tool` | `tools/registry.py`, `mcp/server.py` | **Phase C / spec 05** (folds the duplication) |
| `_get_document` → public `get_document` | `tools/registry.py` (def) + `mcp/server.py` (import) | **Phase C / spec 05** |
| `dispatch`→`run_tool`, `_DISPATCH`→`_TOOL_HANDLERS`, `make_dispatch`→`make_mcp_tool_runner`, inner `dispatch`→`run_tool` | `tools/registry.py`, `mcp/client.py` | **Phase C / specs 05, 03** (non-registry `dispatch_fn`→`run_tool_fn` **is** done here, Task 6) |
| MCP 2-vs-4 tool gap; system prompt still says `escalate` | `mcp/server.py`, `api/agent.py:_SYSTEM` | **Phase C / spec 03** (all tools become real) |
| `list_skills()` dead code + "list-then-load" docstring | `skills/loader.py` | **Phase C / spec 04** (real model-driven selection) |
| `"single source of truth"` docstring vs the duplicated `_hybrid_search` copy | `mcp/server.py` | **Phase C / spec 05** (extract the shared row→dict projection) |
| MCP/Tools/Skills concept banners | `mcp/{client,server}.py`, `tools/registry.py`, `skills/loader.py` | **Phase C** (placed inside the rework; completes the full concept table so `grep "── Concept:"` reaches the manager's 13) |
| Group the 7 `useState`/3 `useRef` in `TriagePage.tsx` into cohesive state objects | `frontend/src/pages/TriagePage.tsx` | **Phase E / spec 08** (that screen is rewritten there) |

**Already satisfied (verify-only, no edit):** spec 02 §D's "one-line header on each of the two waterfall tree-walkers" — the `2026-07-20-timeline-parity` fix already gave `spanTreeToRows` (raw span tree / Observability) and `triageRestoreRows` (restored ticket) descriptive doc-comment headers in `frontend/src/lib/waterfall.ts`. Confirm and skip:
```bash
grep -n 'Flattens a persisted span tree\|Rebuilds a restored ticket' frontend/src/lib/waterfall.ts
```
Expected: both header lines present → no change needed (manufacturing an edit here would be gold-plating).

---

## Self-Review

**Spec 02 coverage:**
- §A name storms — `dispatch_fn`→`run_tool_fn` at the non-registry sites → Task 6. ✅ All registry/MCP-body renames (`hybrid_search` alias/wrapper, `_get_document`, `dispatch`/`_DISPATCH`/`make_dispatch`) explicitly deferred to Phase C with a table. ✅
- §B concept tags — one English `# ── Concept:` banner per non-reworked home + every Portuguese/`topic:` PT tag stripped → Task 1 (9 banners) + Task 2 (PROMPT CACHING) + Task 3 (PARALLELISM). ✅ MCP/Tools/Skills banners deferred to Phase C (documented). ✅
- §C half-built artifacts — `cache_creation_tokens` comment → Task 2; prompt-caching signpost → Task 2; MCP gap / `list_skills` / single-source-of-truth deferred to Phase C. ✅
- §D readability — `_json/_text`, `_accum`, `u1..u5`, semicolons → Task 3; `pool_n` → Task 4; `_first_candidate` → Task 5; waterfall.ts headers already satisfied (verify-only). ✅
- §E test-guarded — centralize `SEARCH_FNS` → Task 7; extract `_dt`→`to_utc` → Task 8; TriagePage state grouping deferred to Phase E. ✅
- Acceptance greps — `── Concept:` (Task 1/2/3 verify), no Portuguese (Task 1 Step 10), no dead-alias/`dispatch_fn` un-annotated (Task 6 + deferral table), behavior green via curl per task. ✅

**Cross-spec rule honored:** no edit touches a `mcp/`, `tools/registry.py`, or `skills/loader.py` *body*; the only leak (`dispatch_fn`) is fixed on the non-reworked `loop.py`/`api/agent.py` side, with the registry-side rename left to Phase C. ✅

**Post-Phase-A paths:** File Structure and all edited paths use post-move names (`api/agent.py`, `rag/embeddings.py` context, `tools/registry.py`/`mcp/*` referenced only in imports/deferrals); every edit anchor avoids the import lines Phase A rewrote. ✅

**Placeholder scan:** no TBD/TODO; complete before/after code for every edit. ✅

**No-test-framework convention:** every task verifies via `restart backend` + `/health` + a targeted curl proving unchanged behavior + grep assertions, then commits — no pytest introduced. ✅

**Name-collision safety:** `_json/_text/_accum/_SEARCH_FNS/_dt` confirmed module-private (no cross-module import); `hybrid_search(pool_n=)` confirmed never passed by any caller; `to_utc` reuse creates no circular import (`runner.py` already imports from `observability`). ✅

# 04 — Tools & multi-agent orchestration (Phases 3–4)

## Purpose
The centerpiece. A **framework-free** orchestrator that delegates to specialized subagents, using
tools, parallelism, and disciplined context management. No LangChain / CrewAI / LangGraph.

## Phase 3 — Tools + single agent

### Tools (topic: "tools")
JSON-schema tools the model can call. Dispatched to Python functions.
| Tool | Input | Returns |
|---|---|---|
| `hybrid_search` | `query`, `k`, `source_type?` | ranked chunks (from spec 02) |
| `get_document` | `document_id` | full doc/ticket text |
| `get_ticket` | `ticket_id` | a past ticket + its resolution |
| `escalate` | `reason` | marks the ticket for a human |

### The tool-use loop (hand-rolled — this is the point)
```
loop:
  resp = await llm.complete(model, system, messages, tools)   # spec-03 provider interface
  append resp (assistant turn) to messages
  if not resp.tool_calls: break
  results = []                      # execute each tool call
  for call in resp.tool_calls:
      out = await dispatch(call.name, call.args)   # mark is_error on failure
      results.append(tool_result(call.id, out))
  append tool results as the next user turn
```
- 🎓 Concepts: the interface normalizes each provider's "please call a tool" signal into `resp.tool_calls`
  (Anthropic `stop_reason=="tool_use"` blocks / Gemini `functionCall` parts). Match each result to its
  `call.id`, return **all** results in one user turn, and flag failures with `is_error` so the model adapts.

### Acceptance
- [ ] A single agent answers one ticket end-to-end using the tools, with citations.

## Phase 4 — Multi-agent orchestration

### Roles (each a subagent with its own context window)
| Subagent | Model role (spec 03) | Job | Returns (structured) |
|---|---|---|---|
| **Classifier** | `MODEL_CLASSIFY` (cheap: flash-lite / haiku) | category / priority / sentiment | `{category, priority, sentiment}` |
| **Retriever** ×N | `MODEL_RESOLVE` (mid: flash / sonnet) | gather evidence for one sub-question via `hybrid_search` | compact summary + cited chunk ids |
| **Resolver** | `MODEL_RESOLVE` (mid: flash / sonnet) | draft the reply grounded in evidence | `{draft, citations[]}` |
| **Critic** | `MODEL_CRITIC` (top: pro / opus) | policy + citation-coverage + hallucination check | `{verdict, issues[], fixes[]}` |

### Orchestrator (framework-free)
Plans → decomposes the ticket into sub-questions → **fans out retrievers in parallel** → resolver drafts → critic reviews → (optional one revision) → final. Plain Python control flow; the orchestrator is itself an agent loop whose "tools" are *spawn subagent* calls.

### Gestão de contexto com subagentes (topic)
- Each subagent gets a **fresh, small context**: just its task + the specific inputs it needs.
- Only a **compact summary** returns to the orchestrator — never the subagent's full transcript.
- 🎓 This is the whole reason subagents exist: the orchestrator's context stays small and cheap, and each subagent reasons without noise. Contrast with stuffing everything into one context.

### Paralelismo (topic)
- Retriever subagents run concurrently with `asyncio.gather` (Python 3.11 `TaskGroup` if we want structured concurrency).
- 🎓 Wall-clock ≈ slowest retriever, not the sum. We'll log sequential-vs-parallel timing to prove it.
- Independent tool calls within one agent turn can also execute concurrently.

### Retry & caching here
- Reuse the spec-03 provider layer: SDK retries + our tool-retry decorator; the shared system prompt + tool defs form the cacheable prefix (Claude `cache_control` / Gemini implicit cache) so repeat subagent calls hit the cache.

### Acceptance
- [ ] Parallel retrievers measurably faster than sequential (logged).
- [ ] Orchestrator context stays small (log its token count vs. a naive single-context baseline).
- [ ] Full triage runs end-to-end: classify → retrieve∥ → resolve → critique → final cited answer.
- [ ] Critic catches a deliberately unsupported claim.

## Open questions
- Max retriever fan-out (sub-question count)? Start at ≤4 for the POC; log if we cap.
- Do we let the critic trigger at most one resolver revision, or report only? Default: one revision, then stop.

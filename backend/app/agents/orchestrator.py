"""Multi-agent orchestration (framework-free) — the centerpiece.

Flow:  classify ∥ plan  →  retrieve×N (parallel)  →  resolve  →  critique  →  (1 revision)  → final

Key ideas demonstrated:
- Subagents with ISOLATED context: each helper is a fresh, small LLM call ([user(msg)] only) that
  returns a COMPACT result — the orchestrator never accumulates a giant transcript (subagent context isolation).
- Parallelism: the retriever subagents run concurrently via asyncio.gather; we log parallel-vs-sequential
  wall-clock to prove the speedup.
- Each subagent uses a model tier matched to its job (all flash-lite on Gemini free tier; the
  haiku/sonnet/opus tiering returns at the Claude swap).
"""
# ── Concept: ORCHESTRATION (FRAMEWORK-FREE) ── hand-rolled classify→retrieve→resolve→critique→revision; no LangChain/CrewAI/LangGraph.
import asyncio
import json
import time
from typing import AsyncGenerator, Awaitable, Callable

from pydantic import BaseModel

from app.agents.prompts import PROMPTS
from app.config import settings
from app.llm.base import user
from app.llm.factory import get_provider
from app.observability import Trace, span
from app.rag import search as search_mod
from app.skills.loader import list_skills, load_skill, run_skill_script


class Classification(BaseModel):
    category: str
    priority: str
    sentiment: str


class SubQuestions(BaseModel):
    questions: list[str]


class Critique(BaseModel):
    verdict: str          # "approve" | "revise"
    issues: list[str]
    fixes: list[str]


class SkillSelection(BaseModel):
    names: list[str]          # subset of the offered skill names, [] if none apply


class _RefundFacts(BaseModel):
    days_since_payment: int | None = None
    status: str = ""
    refunded: bool = False
    dispute_open: bool = False
    is_subscription: bool = False
    within_renewal_window: bool = False


# An emit callback lets _run_pipeline report step_start/step_done events as they happen
# (for the SSE endpoint) without changing what it computes. triage() passes a no-op.
EmitFn = Callable[[dict], Awaitable[None]]


async def _noop_emit(_event: dict) -> None:
    pass


def _add_usage(total: dict, usage) -> None:
    total["input_tokens"] += usage.input_tokens
    total["output_tokens"] += usage.output_tokens
    total["cached_tokens"] += usage.cached_tokens


async def _complete_json(model, system, message, schema, max_tokens=1500):
    # thinking_budget=1: structured extraction needs no chain-of-thought, and leaving thinking
    # on can consume the whole output budget and truncate the JSON. The SDK docs say 0 means
    # "disabled", but the live API rejects 0 with 400 INVALID_ARGUMENT for gemini-flash-lite-latest
    # (verified 2026-07-23) — 1 is the smallest accepted budget and is functionally equivalent.
    resp = await get_provider().complete(
        model=model, system=system, messages=[user(message)], max_tokens=max_tokens,
        response_schema=schema, thinking_budget=1,
    )
    return json.loads(resp.text), resp.usage


async def _complete_text(model, system, message, max_tokens=800):
    resp = await get_provider().complete(
        model=model, system=system, messages=[user(message)], max_tokens=max_tokens
    )
    return resp.text, resp.usage


# --- subagents (each: fresh context in, compact result out) ---

# ── Concept: CONTEXT MANAGEMENT (SUBAGENTS) ── each step is a fresh, isolated LLM call; only a compact result returns, never a growing transcript.
async def _classify(ticket: str):
    async with span("classifier", "subagent", model=settings.model_classify) as s:
        result, usage = await _complete_json(
            settings.model_classify, PROMPTS["classify"], ticket, Classification,
        )
        s.record_usage(usage)
        return result, usage


async def _plan(ticket: str):
    async with span("planner", "subagent", model=settings.model_resolve) as s:
        result, usage = await _complete_json(
            settings.model_resolve, PROMPTS["plan"], ticket, SubQuestions,
        )
        s.record_usage(usage)
        return result, usage


async def _retrieve(subquestion: str, search_mode: str = "hybrid"):
    """A retriever subagent: search (hybrid by default), then summarize into a compact, cited evidence note."""
    async with span("retriever", "subagent", model=settings.model_classify) as s:
        t0 = time.time()
        rows = await search_mod.SEARCH_FNS[search_mode](subquestion, k=4)
        evidence = "\n".join(f"- [{r['title']}] {r['content'][:200]}" for r in rows)
        summary, usage = await _complete_text(
            settings.model_classify, PROMPTS["retrieve"],
            f"Question: {subquestion}\n\nEvidence:\n{evidence}",
            max_tokens=300,
        )
        s.record_usage(usage)
        result = {
            "subquestion": subquestion,
            "summary": summary,
            "cited": [
                {"chunk_id": r["id"], "title": r["title"], "source_type": r["source_type"],
                 "snippet": r["content"][:300]}
                for r in rows
            ],
            "seconds": round(time.time() - t0, 2),
        }
        return result, usage


async def _resolve(ticket, classification, evidences, fixes=None, skill_body=None):
    span_name = "resolver:revision" if fixes else "resolver"
    async with span(span_name, "subagent", model=settings.model_resolve) as s:
        findings = "\n\n".join(f"Q: {e['subquestion']}\nFindings: {e['summary']}" for e in evidences)
        extra = f"\n\nRevise the reply to fix these issues: {fixes}" if fixes else ""
        system = PROMPTS["resolve"]
        # On-demand skill: inject the formatter's house style only when we're drafting a reply.
        if skill_body:
            system += "\n\n# House style (follow exactly):\n" + skill_body
        text, usage = await _complete_text(
            settings.model_resolve, system,
            f"Ticket: {ticket}\nClassification: {classification}\n\n{findings}{extra}",
            max_tokens=700,
        )
        s.record_usage(usage)
        return text, usage


async def _critique(ticket, draft, evidences):
    async with span("critic", "subagent", model=settings.model_critic) as s:
        findings = "\n\n".join(e["summary"] for e in evidences)
        result, usage = await _complete_json(
            settings.model_critic, PROMPTS["critique"],
            f"Ticket: {ticket}\n\nFindings:\n{findings}\n\nDraft reply:\n{draft}",
            Critique,
        )
        s.record_usage(usage)
        return result, usage


async def _select_and_run_skills(ticket: str) -> tuple[list[str], str | None, dict | None]:
    """Level 1 -> 2 -> 3 progressive disclosure, driven by the model (not hardcoded):
    show only names+descriptions, let the model pick, load the chosen bodies, and — if
    refund-policy is chosen — run its level-3 script so its verdict shapes the reply."""
    catalog = list_skills()
    listing = "\n".join(f"- {s['name']}: {s['description']}" for s in catalog)
    async with span("skill_select", "subagent", model=settings.model_classify) as s:
        sel, usage = await _complete_json(
            settings.model_classify,
            "Select which skills apply to this support ticket. Choose only from the offered names; "
            f"return an empty list if none apply.\n\nAvailable skills:\n{listing}",
            ticket, SkillSelection,
        )
        s.record_usage(usage)
    valid = {s_["name"] for s_ in catalog}
    names = [n for n in sel.get("names", []) if n in valid]
    # Always include the reply formatter when drafting (house style), even if unselected.
    if "policy-reply-formatter" not in names:
        names.append("policy-reply-formatter")

    bodies = [b for b in (load_skill(n) for n in names) if b]
    body = "\n\n".join(bodies) if bodies else None

    evidence = None
    if "refund-policy" in names:
        # Level 3: extract the facts the script needs, then run it.
        facts, u = await _complete_json(
            settings.model_classify,
            "Extract refund facts from the ticket as JSON. Unknown numbers -> null; unknown "
            "booleans -> false. Fields: days_since_payment (int|null), status "
            "(succeeded|pending|failed|refunded|disputed), refunded (bool), dispute_open (bool), "
            "is_subscription (bool), within_renewal_window (bool).",
            ticket, _RefundFacts,
        )
        async with span("skill_script:refund_eligibility", "tool"):
            run = await run_skill_script("refund-policy", "refund_eligibility.py", facts)
        if run.get("ok"):
            evidence = {"skill": "refund-policy", "script": "refund_eligibility.py",
                        "verdict": run["output"]}
    return names, body, evidence


async def _run_pipeline(ticket: str, max_subquestions: int = 3, use_skill: bool = True,
                         search_mode: str = "hybrid", emit: EmitFn = _noop_emit,
                         trace_name: str = "triage") -> dict:
    """The actual classify->retrieve->resolve->critique->revision pipeline.

    `emit` is called around each phase so a caller (the SSE endpoint, via `triage_events`)
    can surface real, per-step progress. `triage()` passes the no-op default, so this is
    the single implementation behind both the synchronous and streaming entrypoints.

    `trace_name` tags the resulting Observability trace — live requests use the "triage"
    default; `evals/runner.py` passes "eval" so eval runs are distinguishable from real traffic.
    """
    started = time.time()
    usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}

    async def _select_emit():
        # Progressive disclosure: model-driven skill selection (+ level-3 run) when drafting a reply.
        # Runs INSIDE the trace (below) so skill_select / skill_script spans attach to it.
        if not use_skill:
            return [], None, None
        return await _select_and_run_skills(ticket)

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

    async with Trace(trace_name) as trace:
        # 1) classify + plan + skill-selection concurrently (all independent)
        # ── Concept: PARALLELISM ── classify + plan + skill-selection (and below, all retrievers) run concurrently via asyncio.gather; overlap is provable on span timestamps.
        (classification, classify_usage), (subqs, plan_usage), \
            (selected_names, skill_body, skill_evidence) = await asyncio.gather(
                _classify_emit(), _plan_emit(), _select_emit())
        _add_usage(usage, classify_usage)
        _add_usage(usage, plan_usage)
        questions = subqs["questions"][:max_subquestions]

        # 2) retrievers in parallel — measure parallel vs would-be-sequential wall-clock
        t0 = time.time()
        retrieved = await asyncio.gather(*[_retrieve_emit(i, q) for i, q in enumerate(questions)])
        parallel_seconds = round(time.time() - t0, 2)
        evidences = [r for r, _ in retrieved]
        for _, retrieve_usage in retrieved:
            _add_usage(usage, retrieve_usage)
        sequential_estimate = round(sum(e["seconds"] for e in evidences), 2)

        if skill_evidence:
            v = skill_evidence["verdict"]
            evidences = evidences + [{
                "subquestion": "Refund eligibility (deterministic policy script)",
                "summary": f"refund-policy/refund_eligibility.py -> eligible={v['eligible']}, "
                           f"method={v['method']}: {v['reason']}",
            }]

        # 3) resolve  4) critique  (+ one revision if the critic asks)
        await emit({"type": "step_start", "step": "resolve"})
        draft, draft_usage = await _resolve(ticket, classification, evidences, skill_body=skill_body)
        _add_usage(usage, draft_usage)
        await emit({"type": "step_done", "step": "resolve", "data": {"draft": draft}})

        await emit({"type": "step_start", "step": "critique"})
        critique, critique_usage = await _critique(ticket, draft, evidences)
        _add_usage(usage, critique_usage)
        await emit({"type": "step_done", "step": "critique", "data": critique})

        revised = None
        if critique.get("verdict") != "approve":
            await emit({"type": "step_start", "step": "revise"})
            revised, revise_usage = await _resolve(ticket, classification, evidences,
                                                   fixes=critique.get("fixes"), skill_body=skill_body)
            _add_usage(usage, revise_usage)
            await emit({"type": "step_done", "step": "revise", "data": {"revised": revised}})
        final = revised or draft

        result = {
            "ticket": ticket,
            "classification": classification,
            "subquestions": questions,
            "evidence": evidences,
            "draft": draft,
            "critique": critique,
            "revised": revised is not None,
            "skills_used": selected_names,
            "skill_evidence": skill_evidence,   # {"skill","script","verdict"} or None -> UI badge
            "final_reply": final,
            "parallelism": {
                "retrievers": len(questions),
                "parallel_seconds": parallel_seconds,
                "sequential_estimate_seconds": sequential_estimate,
                "speedup": round(sequential_estimate / parallel_seconds, 2) if parallel_seconds else None,
            },
            "usage": usage,
            "total_seconds": round(time.time() - started, 2),
        }

    result["trace_id"] = trace.id
    result["cost_usd"] = trace.total_cost_usd
    return result


async def triage_events(ticket: str, max_subquestions: int = 3, use_skill: bool = True,
                         search_mode: str = "hybrid", trace_name: str = "triage") -> AsyncGenerator[dict, None]:
    """Streaming entrypoint: yields step_start/step_done events as the pipeline actually runs,
    then a final `{"type": "final", "result": ...}` event.

    Runs `_run_pipeline` as a background task so events from concurrent phases (classify∥plan,
    the parallel retrievers) can be put on the queue as soon as each finishes, rather than
    batched at the end of an `asyncio.gather`. `asyncio.create_task` copies the current
    contextvars context at creation time, so the Trace/span contextvars set inside the task
    still propagate correctly to its own nested `asyncio.gather` children — identical to how
    the parallel retrievers already relied on this before streaming existed.
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def run():
        try:
            result = await _run_pipeline(
                ticket, max_subquestions=max_subquestions, use_skill=use_skill,
                search_mode=search_mode, emit=queue.put, trace_name=trace_name,
            )
            await queue.put({"type": "final", "result": result})
        except Exception as exc:  # noqa: BLE001 - re-raised below, not swallowed
            await queue.put({"type": "__error__", "exc": exc})
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            if item["type"] == "__error__":
                raise item["exc"]
            yield item
    finally:
        await task


async def triage(ticket: str, max_subquestions: int = 3, use_skill: bool = True,
                  search_mode: str = "hybrid", trace_name: str = "triage") -> dict:
    """Synchronous entrypoint (unchanged behavior/signature by default) — drains `triage_events`
    and returns the final result, exactly as before streaming existed."""
    async for event in triage_events(
        ticket, max_subquestions=max_subquestions, use_skill=use_skill, search_mode=search_mode,
        trace_name=trace_name,
    ):
        if event["type"] == "final":
            return event["result"]
    raise RuntimeError("triage_events ended without a final event")

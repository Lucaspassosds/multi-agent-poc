"""Multi-agent orchestration (framework-free) — the centerpiece.

Flow:  classify ∥ plan  →  retrieve×N (parallel)  →  resolve  →  critique  →  (1 revision)  → final

Key ideas demonstrated:
- Subagents with ISOLATED context: each helper is a fresh, small LLM call ([user(msg)] only) that
  returns a COMPACT result — the orchestrator never accumulates a giant transcript (gestão de contexto).
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

from app.config import settings
from app.llm.base import user
from app.llm.factory import get_provider
from app.observability import Trace, span
from app.rag import search as search_mod
from app.skills import load_skill

# Retrieval mode dispatch — same dict-dispatch pattern as main.py's /search. Defaulting a
# retriever to "lexical" or "semantic" lets Phase 7 evals demonstrate a deliberate regression
# (hybrid is strictly better) without duplicating the orchestrator flow.
_SEARCH_FNS = {
    "lexical": search_mod.lexical_search,
    "semantic": search_mod.semantic_search,
    "hybrid": search_mod.hybrid_search,
}


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


# An emit callback lets _run_pipeline report step_start/step_done events as they happen
# (for the SSE endpoint) without changing what it computes. triage() passes a no-op.
EmitFn = Callable[[dict], Awaitable[None]]


async def _noop_emit(_event: dict) -> None:
    pass


def _accum(total: dict, usage) -> None:
    total["input_tokens"] += usage.input_tokens
    total["output_tokens"] += usage.output_tokens
    total["cached_tokens"] += usage.cached_tokens


async def _json(model, system, message, schema, max_tokens=1500):
    # thinking_budget=1: structured extraction needs no chain-of-thought, and leaving thinking
    # on can consume the whole output budget and truncate the JSON. The SDK docs say 0 means
    # "disabled", but the live API rejects 0 with 400 INVALID_ARGUMENT for gemini-flash-lite-latest
    # (verified 2026-07-23) — 1 is the smallest accepted budget and is functionally equivalent.
    resp = await get_provider().complete(
        model=model, system=system, messages=[user(message)], max_tokens=max_tokens,
        response_schema=schema, thinking_budget=1,
    )
    return json.loads(resp.text), resp.usage


async def _text(model, system, message, max_tokens=800):
    resp = await get_provider().complete(
        model=model, system=system, messages=[user(message)], max_tokens=max_tokens
    )
    return resp.text, resp.usage


# --- subagents (each: fresh context in, compact result out) ---

# ── Concept: CONTEXT MANAGEMENT (SUBAGENTS) ── each step is a fresh, isolated LLM call; only a compact result returns, never a growing transcript.
async def _classify(ticket: str):
    async with span("classifier", "subagent", model=settings.model_classify) as s:
        result, usage = await _json(
            settings.model_classify,
            "Classify the support ticket. category in {billing,refund,subscription,payment_failure,dispute,other}; "
            "priority in {low,medium,high}; sentiment in {angry,neutral,happy}.",
            ticket, Classification,
        )
        s.record_usage(usage)
        return result, usage


async def _plan(ticket: str):
    async with span("planner", "subagent", model=settings.model_resolve) as s:
        result, usage = await _json(
            settings.model_resolve,
            "Plan retrieval for this support ticket. Produce 2-3 focused search sub-questions that will surface "
            "the KB articles and past tickets needed to resolve it.",
            ticket, SubQuestions,
        )
        s.record_usage(usage)
        return result, usage


async def _retrieve(subquestion: str, search_mode: str = "hybrid"):
    """A retriever subagent: search (hybrid by default), then summarize into a compact, cited evidence note."""
    async with span("retriever", "subagent", model=settings.model_classify) as s:
        t0 = time.time()
        rows = await _SEARCH_FNS[search_mode](subquestion, k=4)
        evidence = "\n".join(f"- [{r['title']}] {r['content'][:200]}" for r in rows)
        summary, usage = await _text(
            settings.model_classify,
            "Summarize the evidence into 2-3 sentences that answer the question. Cite sources as [title]. "
            "Use ONLY the evidence provided.",
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
        system = (
            "You are a payments support agent. Write a concise, friendly, customer-ready reply grounded ONLY in "
            "the findings. Cite article titles in-line. Never invent policy."
        )
        # On-demand skill: inject the formatter's house style only when we're drafting a reply.
        if skill_body:
            system += "\n\n# House style (follow exactly):\n" + skill_body
        text, usage = await _text(
            settings.model_resolve, system,
            f"Ticket: {ticket}\nClassification: {classification}\n\n{findings}{extra}",
            max_tokens=700,
        )
        s.record_usage(usage)
        return text, usage


async def _critique(ticket, draft, evidences):
    async with span("critic", "subagent", model=settings.model_critic) as s:
        findings = "\n\n".join(e["summary"] for e in evidences)
        result, usage = await _json(
            settings.model_critic,
            "You are a QA critic. Check the draft reply against the findings for unsupported claims "
            "(hallucination), missing policy points, and wrong tone. verdict='approve' if solid, else 'revise'. "
            "List concrete issues and fixes.",
            f"Ticket: {ticket}\n\nFindings:\n{findings}\n\nDraft reply:\n{draft}",
            Critique,
        )
        s.record_usage(usage)
        return result, usage


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
    # Progressive disclosure: load the formatter skill body only when we'll draft a reply.
    skill_body = load_skill("policy-reply-formatter") if use_skill else None

    async def _classify_emit():
        await emit({"type": "step_start", "step": "classify"})
        result, u = await _classify(ticket)
        await emit({"type": "step_done", "step": "classify", "data": result})
        return result, u

    async def _plan_emit():
        await emit({"type": "step_start", "step": "plan"})
        result, u = await _plan(ticket)
        await emit({"type": "step_done", "step": "plan", "data": result})
        return result, u

    async def _retrieve_emit(index: int, subquestion: str):
        await emit({"type": "step_start", "step": "retrieve", "index": index, "subquestion": subquestion})
        result, u = await _retrieve(subquestion, search_mode)
        await emit({"type": "step_done", "step": "retrieve", "index": index, "data": result})
        return result, u

    async with Trace(trace_name) as trace:
        # 1) classify + plan concurrently (independent)
        # ── Concept: PARALLELISM ── classify + plan (and below, all retrievers) run concurrently via asyncio.gather; overlap is provable on span timestamps.
        (classification, u1), (subqs, u2) = await asyncio.gather(_classify_emit(), _plan_emit())
        _accum(usage, u1); _accum(usage, u2)
        questions = subqs["questions"][:max_subquestions]

        # 2) retrievers in parallel — measure parallel vs would-be-sequential wall-clock
        t0 = time.time()
        retrieved = await asyncio.gather(*[_retrieve_emit(i, q) for i, q in enumerate(questions)])
        parallel_seconds = round(time.time() - t0, 2)
        evidences = [r for r, _ in retrieved]
        for _, u in retrieved:
            _accum(usage, u)
        sequential_estimate = round(sum(e["seconds"] for e in evidences), 2)

        # 3) resolve  4) critique  (+ one revision if the critic asks)
        await emit({"type": "step_start", "step": "resolve"})
        draft, u3 = await _resolve(ticket, classification, evidences, skill_body=skill_body); _accum(usage, u3)
        await emit({"type": "step_done", "step": "resolve", "data": {"draft": draft}})

        await emit({"type": "step_start", "step": "critique"})
        critique, u4 = await _critique(ticket, draft, evidences); _accum(usage, u4)
        await emit({"type": "step_done", "step": "critique", "data": critique})

        revised = None
        if critique.get("verdict") != "approve":
            await emit({"type": "step_start", "step": "revise"})
            revised, u5 = await _resolve(ticket, classification, evidences,
                                         fixes=critique.get("fixes"), skill_body=skill_body)
            _accum(usage, u5)
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
            "skill_used": "policy-reply-formatter" if skill_body else None,
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

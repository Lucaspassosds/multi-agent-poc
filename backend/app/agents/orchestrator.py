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
import asyncio
import json
import time

from pydantic import BaseModel

from app.config import settings
from app.llm.base import user
from app.llm.factory import get_provider
from app.rag.search import hybrid_search
from app.skills import load_skill


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


def _accum(total: dict, usage) -> None:
    total["input_tokens"] += usage.input_tokens
    total["output_tokens"] += usage.output_tokens
    total["cached_tokens"] += usage.cached_tokens


async def _json(model, system, message, schema, max_tokens=1500):
    # thinking_budget=0: structured extraction needs no chain-of-thought, and leaving it on
    # can consume the whole output budget and truncate the JSON.
    resp = await get_provider().complete(
        model=model, system=system, messages=[user(message)], max_tokens=max_tokens,
        response_schema=schema, thinking_budget=0,
    )
    return json.loads(resp.text), resp.usage


async def _text(model, system, message, max_tokens=800):
    resp = await get_provider().complete(
        model=model, system=system, messages=[user(message)], max_tokens=max_tokens
    )
    return resp.text, resp.usage


# --- subagents (each: fresh context in, compact result out) ---

async def _classify(ticket: str):
    return await _json(
        settings.model_classify,
        "Classify the support ticket. category in {billing,refund,subscription,payment_failure,dispute,other}; "
        "priority in {low,medium,high}; sentiment in {angry,neutral,happy}.",
        ticket, Classification,
    )


async def _plan(ticket: str):
    return await _json(
        settings.model_resolve,
        "Plan retrieval for this support ticket. Produce 2-3 focused search sub-questions that will surface "
        "the KB articles and past tickets needed to resolve it.",
        ticket, SubQuestions,
    )


async def _retrieve(subquestion: str):
    """A retriever subagent: hybrid_search, then summarize into a compact, cited evidence note."""
    t0 = time.time()
    rows = await hybrid_search(subquestion, k=4)
    evidence = "\n".join(f"- [{r['title']}] {r['content'][:200]}" for r in rows)
    summary, usage = await _text(
        settings.model_classify,
        "Summarize the evidence into 2-3 sentences that answer the question. Cite sources as [title]. "
        "Use ONLY the evidence provided.",
        f"Question: {subquestion}\n\nEvidence:\n{evidence}",
        max_tokens=300,
    )
    result = {
        "subquestion": subquestion,
        "summary": summary,
        "cited": [{"chunk_id": r["id"], "title": r["title"], "source_type": r["source_type"]} for r in rows],
        "seconds": round(time.time() - t0, 2),
    }
    return result, usage


async def _resolve(ticket, classification, evidences, fixes=None, skill_body=None):
    findings = "\n\n".join(f"Q: {e['subquestion']}\nFindings: {e['summary']}" for e in evidences)
    extra = f"\n\nRevise the reply to fix these issues: {fixes}" if fixes else ""
    system = (
        "You are a payments support agent. Write a concise, friendly, customer-ready reply grounded ONLY in "
        "the findings. Cite article titles in-line. Never invent policy."
    )
    # On-demand skill: inject the formatter's house style only when we're drafting a reply.
    if skill_body:
        system += "\n\n# House style (follow exactly):\n" + skill_body
    return await _text(
        settings.model_resolve, system,
        f"Ticket: {ticket}\nClassification: {classification}\n\n{findings}{extra}",
        max_tokens=700,
    )


async def _critique(ticket, draft, evidences):
    findings = "\n\n".join(e["summary"] for e in evidences)
    return await _json(
        settings.model_critic,
        "You are a QA critic. Check the draft reply against the findings for unsupported claims "
        "(hallucination), missing policy points, and wrong tone. verdict='approve' if solid, else 'revise'. "
        "List concrete issues and fixes.",
        f"Ticket: {ticket}\n\nFindings:\n{findings}\n\nDraft reply:\n{draft}",
        Critique,
    )


async def triage(ticket: str, max_subquestions: int = 3, use_skill: bool = True) -> dict:
    started = time.time()
    usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
    # Progressive disclosure: load the formatter skill body only when we'll draft a reply.
    skill_body = load_skill("policy-reply-formatter") if use_skill else None

    # 1) classify + plan concurrently (independent)
    (classification, u1), (subqs, u2) = await asyncio.gather(_classify(ticket), _plan(ticket))
    _accum(usage, u1); _accum(usage, u2)
    questions = subqs["questions"][:max_subquestions]

    # 2) retrievers in parallel — measure parallel vs would-be-sequential wall-clock
    t0 = time.time()
    retrieved = await asyncio.gather(*[_retrieve(q) for q in questions])
    parallel_seconds = round(time.time() - t0, 2)
    evidences = [r for r, _ in retrieved]
    for _, u in retrieved:
        _accum(usage, u)
    sequential_estimate = round(sum(e["seconds"] for e in evidences), 2)

    # 3) resolve  4) critique  (+ one revision if the critic asks)
    draft, u3 = await _resolve(ticket, classification, evidences, skill_body=skill_body); _accum(usage, u3)
    critique, u4 = await _critique(ticket, draft, evidences); _accum(usage, u4)
    revised = None
    if critique.get("verdict") != "approve":
        revised, u5 = await _resolve(ticket, classification, evidences,
                                     fixes=critique.get("fixes"), skill_body=skill_body)
        _accum(usage, u5)
    final = revised or draft

    return {
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

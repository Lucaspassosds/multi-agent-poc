"""LLM-rerank over a fused candidate pool (topic: RAG) — the single biggest quality win, and NOT
a training pipeline. One structured LLM call scores each fused candidate 0-1 for how well it
answers the query; we keep the top_k, adding a rerank_score + a short 'why' per survivor so the
reordering is inspectable. Runs inside a 'reranker' span so it shows up in the trace.
"""
import json

from pydantic import BaseModel

from app.config import settings
from app.llm.base import user
from app.llm.factory import get_provider
from app.observability import span


class _Ranked(BaseModel):
    id: int
    relevance: float   # 0-1
    why: str


class _RerankOut(BaseModel):
    ranked: list[_Ranked]


async def rerank(query: str, results: list[dict], top_k: int = 4) -> list[dict]:
    if not results:
        return results
    async with span("reranker", "subagent", model=settings.model_classify) as s:
        catalogue = "\n".join(
            f"[{r['id']}] {r.get('title','')}: {r['content'][:200]}" for r in results
        )
        out, usage = await _rerank_call(query, catalogue)
        s.record_usage(usage)

    order = {r.id: (r.relevance, r.why) for r in out.ranked}
    ranked = sorted(
        results, key=lambda r: order.get(r["id"], (0.0, ""))[0], reverse=True
    )[:top_k]
    for r in ranked:
        rel, why = order.get(r["id"], (None, None))
        r["rerank_score"] = rel
        r["why"] = why
    return ranked


async def _rerank_call(query: str, catalogue: str):
    resp = await get_provider().complete(
        model=settings.model_classify,
        system=("Score each candidate document 0-1 for how directly it answers the question. "
                "Return every candidate id with a relevance score and a one-line reason."),
        messages=[user(f"Question: {query}\n\nCandidates:\n{catalogue}")],
        max_tokens=800,
        response_schema=_RerankOut,
        # thinking_budget=1, not 0: the live Gemini API rejects 0 with 400 INVALID_ARGUMENT
        # for gemini-flash-lite-latest (same documented constraint as _complete_json above);
        # 1 is the smallest accepted budget and is functionally equivalent to "disabled".
        thinking_budget=1,
    )
    return _RerankOut(**json.loads(resp.text)), resp.usage

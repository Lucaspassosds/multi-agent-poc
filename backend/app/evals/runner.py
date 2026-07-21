"""Phase 7 — run the golden set through the full triage pipeline and score it.

Reuses `orchestrator.triage()` as-is, so each case is also a Phase-6 trace (cost of an eval run
is visible via GET /traces, tagged trace_name="eval" so it's distinguishable from live "triage"
traffic) plus one extra LLM-as-judge call per case. `retrieval_mode` lets a demo force
lexical/semantic-only retrieval to show a deliberate regression (spec's acceptance criterion:
"a deliberate regression measurably lowers the scores").
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.agents.orchestrator import triage
from app.config import settings
from app.db import get_pool
from app.evals.judge import judge
from app.evals.metrics import citation_coverage, classification_match, retrieval_hit
from app.observability import cost_usd

_GOLDEN_PATH = Path(__file__).parent / "golden.json"
# Gemini free tier caps at 15 requests/MINUTE for this model, and a single triage() case alone
# fires ~7-8 calls in a few seconds — running cases concurrently would only stack more bursts on
# top of an already-saturated quota. Sequential + with_retry's RetryInfo-aware backoff (see
# app/llm/retry.py) is what actually gets 20 cases through; concurrency here would just add noise.
_CONCURRENCY = 1


def _load_golden() -> list[dict]:
    return json.loads(_GOLDEN_PATH.read_text())


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


async def _run_case(case: dict, search_mode: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        result = await triage(case["ticket"], search_mode=search_mode, trace_name="eval")
        verdict, judge_usage = await judge(case, result)

    category_correct, priority_correct = classification_match(case, result)
    judge_cost = cost_usd(settings.model_critic, judge_usage.input_tokens, judge_usage.output_tokens)

    return {
        "golden_id": case["id"],
        "ticket": case["ticket"],
        "trace_id": result.get("trace_id"),
        "predicted_category": result["classification"].get("category"),
        "expected_category": case["expected_category"],
        "category_correct": category_correct,
        "predicted_priority": result["classification"].get("priority"),
        "expected_priority": case["expected_priority"],
        "priority_correct": priority_correct,
        "retrieval_hit": retrieval_hit(case, result),
        "citation_coverage": citation_coverage(result),
        "faithfulness_score": verdict["faithfulness_score"],
        "faithfulness_reasoning": verdict["faithfulness_reasoning"],
        "helpfulness_score": verdict["helpfulness_score"],
        "helpfulness_reasoning": verdict["helpfulness_reasoning"],
        "final_reply": result["final_reply"],
        "cost_usd": round(result.get("cost_usd", 0.0) + judge_cost, 6),
    }


def _rate(cases: list[dict], key: str) -> float:
    n = len(cases)
    return round(sum(1 for c in cases if c[key]) / n, 4) if n else 0.0


def _avg(cases: list[dict], key: str) -> float:
    n = len(cases)
    return round(sum(c[key] for c in cases) / n, 4) if n else 0.0


async def _persist(retrieval_mode: str, started: float, ended: float,
                    per_case: list[dict], aggregate: dict) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn, conn.transaction():
        run_id = await conn.fetchval(
            """INSERT INTO eval_runs (started_at, ended_at, retrieval_mode, n_cases,
                                       classification_accuracy, priority_accuracy,
                                       retrieval_hit_rate, citation_coverage,
                                       faithfulness_avg, helpfulness_avg, total_cost_usd)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id""",
            _dt(started), _dt(ended), retrieval_mode, aggregate["n_cases"],
            aggregate["classification_accuracy"], aggregate["priority_accuracy"],
            aggregate["retrieval_hit_rate"], aggregate["citation_coverage"],
            aggregate["faithfulness_avg"], aggregate["helpfulness_avg"], aggregate["total_cost_usd"],
        )
        for c in per_case:
            await conn.execute(
                """INSERT INTO eval_cases (run_id, golden_id, ticket, trace_id,
                                            predicted_category, expected_category, category_correct,
                                            predicted_priority, expected_priority, priority_correct,
                                            retrieval_hit, citation_coverage,
                                            faithfulness_score, faithfulness_reasoning,
                                            helpfulness_score, helpfulness_reasoning, final_reply)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)""",
                run_id, c["golden_id"], c["ticket"], c["trace_id"],
                c["predicted_category"], c["expected_category"], c["category_correct"],
                c["predicted_priority"], c["expected_priority"], c["priority_correct"],
                c["retrieval_hit"], c["citation_coverage"],
                c["faithfulness_score"], c["faithfulness_reasoning"],
                c["helpfulness_score"], c["helpfulness_reasoning"], c["final_reply"],
            )
    return run_id


async def run_eval(retrieval_mode: str = "hybrid") -> dict:
    started = time.time()
    cases = _load_golden()
    sem = asyncio.Semaphore(_CONCURRENCY)
    per_case = await asyncio.gather(*[_run_case(c, retrieval_mode, sem) for c in cases])
    ended = time.time()
    per_case = list(per_case)

    aggregate = {
        "n_cases": len(per_case),
        "classification_accuracy": _rate(per_case, "category_correct"),
        "priority_accuracy": _rate(per_case, "priority_correct"),
        "retrieval_hit_rate": _rate(per_case, "retrieval_hit"),
        "citation_coverage": _avg(per_case, "citation_coverage"),
        "faithfulness_avg": _avg(per_case, "faithfulness_score"),
        "helpfulness_avg": _avg(per_case, "helpfulness_score"),
        "total_cost_usd": round(sum(c["cost_usd"] for c in per_case), 6),
    }

    run_id = await _persist(retrieval_mode, started, ended, per_case, aggregate)

    return {
        "id": run_id,
        "retrieval_mode": retrieval_mode,
        "started_at": _dt(started).isoformat(),
        "ended_at": _dt(ended).isoformat(),
        **aggregate,
        "cases": per_case,
    }

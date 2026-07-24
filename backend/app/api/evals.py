"""Phase 7 — run the golden-set eval suite and read back the latest run."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.db import get_pool
from app.evals.runner import run_eval

router = APIRouter(prefix="/evals", tags=["evals"])

_BASELINE_PATH = Path(__file__).parent.parent / "evals" / "baseline.json"


def _as_json(value, default):
    # asyncpg returns JSONB as a str (no decoder registered on this pool); normalize to Python data.
    if value is None:
        return default
    return json.loads(value) if isinstance(value, str) else value


@router.post("/run")
async def run(retrieval_mode: str = Query("hybrid", pattern="^(lexical|semantic|hybrid)$")):
    """Run the full golden set through the triage pipeline + LLM-judge. `retrieval_mode=lexical`
    (or `semantic`) forces degraded retrieval — the regression demo."""
    return await run_eval(retrieval_mode=retrieval_mode)


@router.get("")
async def latest():
    """The most recent eval run: aggregate scores + per-case breakdown."""
    pool = await get_pool()
    run_row = await pool.fetchrow("SELECT * FROM eval_runs ORDER BY started_at DESC LIMIT 1")
    if run_row is None:
        raise HTTPException(status_code=404, detail="no eval runs yet — POST /evals/run first")

    case_rows = await pool.fetch(
        "SELECT * FROM eval_cases WHERE run_id = $1 ORDER BY id", run_row["id"]
    )
    return {
        "id": run_row["id"],
        "retrieval_mode": run_row["retrieval_mode"],
        "started_at": run_row["started_at"].isoformat(),
        "ended_at": run_row["ended_at"].isoformat(),
        "n_cases": run_row["n_cases"],
        "classification_accuracy": float(run_row["classification_accuracy"]),
        "priority_accuracy": float(run_row["priority_accuracy"]),
        "retrieval_hit_rate": float(run_row["retrieval_hit_rate"]),
        "citation_coverage": float(run_row["citation_coverage"]),
        "faithfulness_avg": float(run_row["faithfulness_avg"]),
        "helpfulness_avg": float(run_row["helpfulness_avg"]),
        "total_cost_usd": float(run_row["total_cost_usd"]),
        "failure_breakdown": _as_json(run_row["failure_breakdown"], default={}),
        "regression": run_row["regression"],
        "cases": [
            {
                "golden_id": r["golden_id"],
                "ticket": r["ticket"],
                "trace_id": r["trace_id"],
                "predicted_category": r["predicted_category"],
                "expected_category": r["expected_category"],
                "category_correct": r["category_correct"],
                "predicted_priority": r["predicted_priority"],
                "expected_priority": r["expected_priority"],
                "priority_correct": r["priority_correct"],
                "retrieval_hit": r["retrieval_hit"],
                "citation_coverage": float(r["citation_coverage"]),
                "faithfulness_score": float(r["faithfulness_score"]),
                "faithfulness_reasoning": r["faithfulness_reasoning"],
                "helpfulness_score": float(r["helpfulness_score"]),
                "helpfulness_reasoning": r["helpfulness_reasoning"],
                "final_reply": r["final_reply"],
                "failure_labels": _as_json(r["failure_labels"], default=[]),
            }
            for r in case_rows
        ],
    }


@router.post("/baseline")
async def bless_baseline():
    """Freeze the latest run's aggregate as the regression baseline."""
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM eval_runs ORDER BY started_at DESC LIMIT 1")
    if row is None:
        raise HTTPException(status_code=404, detail="no eval runs yet")
    baseline = {
        "retrieval_mode": row["retrieval_mode"],
        "classification_accuracy": float(row["classification_accuracy"]),
        "priority_accuracy": float(row["priority_accuracy"]),
        "retrieval_hit_rate": float(row["retrieval_hit_rate"]),
        "citation_coverage": float(row["citation_coverage"]),
        "faithfulness_avg": float(row["faithfulness_avg"]),
        "helpfulness_avg": float(row["helpfulness_avg"]),
    }
    _BASELINE_PATH.write_text(json.dumps(baseline, indent=2))
    return {"blessed": True, "baseline": baseline}

"""LLM-as-judge — scores what deterministic metrics can't: whether the reply is
actually grounded in evidence and whether it resolves the ticket. One structured call per case
(both dimensions together, not two separate calls) to conserve free-tier quota.
"""
# ── Concept: EVALS (LLM-as-judge) ── one structured call scores faithfulness + helpfulness the metrics can't measure.
import json

from pydantic import BaseModel

from app.agents.prompts import PROMPTS
from app.config import settings
from app.llm.base import user
from app.llm.factory import get_provider


class JudgeVerdict(BaseModel):
    faithfulness_score: float    # 0-1: does the reply ONLY make claims the evidence supports?
    faithfulness_reasoning: str
    helpfulness_score: float     # 0-1: does the reply resolve the ticket, vs. the reference answer?
    helpfulness_reasoning: str


async def judge(case: dict, result: dict):
    evidence = "\n".join(f"- {e['summary']}" for e in result["evidence"])
    prompt = (
        f"Ticket: {case['ticket']}\n\n"
        f"Retrieved evidence:\n{evidence}\n\n"
        f"Reference answer (for comparison only, not the only acceptable phrasing):\n"
        f"{case['reference_answer']}\n\n"
        f"Agent's actual reply:\n{result['final_reply']}\n\n"
        "Score faithfulness (0-1): does the reply ONLY make claims supported by the retrieved "
        "evidence, with no invented policy? Score helpfulness (0-1): does the reply resolve the "
        "ticket as well as the reference answer does? Give brief, concrete reasoning for each score."
    )
    resp = await get_provider().complete(
        model=settings.model_critic,
        system=PROMPTS["judge"],
        messages=[user(prompt)],
        max_tokens=500,
        response_schema=JudgeVerdict,
        thinking_budget=1,  # smallest budget the live API accepts for this model; 0 gets 400 INVALID_ARGUMENT
    )
    return json.loads(resp.text), resp.usage

"""Phase 3 endpoint — a single tool-using agent that answers a support ticket."""
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.agents.loop import run_agent
from app.agents.orchestrator import triage
from app.config import settings
from app.mcp_client import list_tool_specs, make_dispatch, mcp_session

router = APIRouter(prefix="/agent", tags=["agent"])

_SYSTEM = (
    "You are a payments support triage assistant. "
    "ALWAYS call hybrid_search to find relevant KB articles and past tickets before answering. "
    "Ground your answer in what you find and cite sources by their title. "
    "If the issue cannot be resolved from available information, call escalate. "
    "Keep the final reply concise and customer-ready."
)


class AgentIn(BaseModel):
    message: str


@router.post("/answer")
async def answer(body: AgentIn):
    return await run_agent(system=_SYSTEM, message=body.message, model=settings.model_resolve)


@router.post("/triage")
async def triage_endpoint(
    body: AgentIn, skill: bool = Query(True),
    search_mode: str = Query("hybrid", pattern="^(lexical|semantic|hybrid)$"),
):
    """Full multi-agent pipeline: classify → retrieve (parallel) → resolve → critique → final.

    `skill=false` disables the policy-reply-formatter skill (to show its effect). `search_mode`
    forces the retrievers onto lexical/semantic-only search (Phase 7's regression demo)."""
    return await triage(body.message, use_skill=skill, search_mode=search_mode)


@router.post("/answer-mcp")
async def answer_mcp(body: AgentIn):
    """Same single-agent loop as /answer, but tools come from the MCP server over the protocol."""
    async with mcp_session() as session:
        tools = await list_tool_specs(session)
        dispatch = make_dispatch(session)
        result = await run_agent(
            system=_SYSTEM, message=body.message, model=settings.model_resolve,
            tools=tools, dispatch_fn=dispatch,
        )
        result["tools_source"] = "mcp"
        result["mcp_tools"] = [t.name for t in tools]
        return result

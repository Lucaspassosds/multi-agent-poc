"""Phase 3 endpoint — a single tool-using agent that answers a support ticket."""
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.loop import run_agent
from app.agents.orchestrator import triage, triage_events
from app.api_tickets import save_ticket
from app.config import settings
from app.mcp.client import list_tool_specs, make_dispatch, mcp_session

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
    session_id: str | None = None  # anonymous per-visitor history key; None → don't persist


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


@router.post("/triage/stream")
async def triage_stream_endpoint(
    body: AgentIn, skill: bool = Query(True),
    search_mode: str = Query("hybrid", pattern="^(lexical|semantic|hybrid)$"),
):
    """Same pipeline as `/agent/triage`, streamed live over SSE (Phase 8): a `step_start`/
    `step_done` event per phase (classify, plan, retrieve×N, resolve, critique, revise) as it
    actually happens — including real overlap for the concurrent phases — then one `final`
    event carrying the same result shape `/agent/triage` returns. Mirrors the `data: ...\\n\\n`
    + `[DONE]` sentinel convention already used by `GET /llm/stream`. POST (not GET) because the
    ticket is a body, not a query string, so the client must use fetch-stream, not `EventSource`.
    """
    async def gen():
        final_result = None
        errored = False
        try:
            async for event in triage_events(body.message, use_skill=skill, search_mode=search_mode):
                if event.get("type") == "final":
                    final_result = event.get("result")
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:  # noqa: BLE001 - surfaced to the client as an SSE event
            errored = True
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        # Persist only a completed, successful run — never on error, never without a session.
        if not errored and final_result is not None and body.session_id:
            try:
                await save_ticket(body.session_id, final_result)
            except Exception as exc:  # noqa: BLE001 - persistence must not break the stream
                print(f"[tickets] failed to persist ticket: {exc}")

        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


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

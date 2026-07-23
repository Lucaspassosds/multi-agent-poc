"""The hand-rolled tool-use loop (topic: "orquestração sem framework").

No LangChain/CrewAI — just: call the model, if it asked for tools run them, feed the
results back, repeat until it produces a final answer (or we hit the iteration cap).
Every step is recorded for observability (Phase 6).
"""
# ── Concept: TOOLS (THE HAND-ROLLED LOOP) ── call model → run requested tools → feed results back → repeat until final. No framework.
from app.tools import TOOL_SPECS, dispatch
from app.llm.base import Message, ToolSpec, assistant, tool_result, user
from app.llm.factory import get_provider
from app.observability import Trace, span


async def run_agent(
    *,
    system: str,
    message: str,
    model: str,
    tools: list[ToolSpec] = TOOL_SPECS,
    dispatch_fn=dispatch,
    max_iters: int = 6,
) -> dict:
    # dispatch_fn defaults to the in-process tools; the MCP path (spec 05) passes a
    # dispatch that calls tools over the protocol instead — same loop either way.
    provider = get_provider()
    messages: list[Message] = [user(message)]
    steps: list[dict] = []
    usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}

    async with Trace("agent") as trace:
        result = None
        for i in range(max_iters):
            async with span("llm_call", "llm_call", model=model) as s:
                resp = await provider.complete(
                    model=model, system=system, messages=messages, tools=tools, max_tokens=1024
                )
                s.record_usage(resp.usage)
            usage["input_tokens"] += resp.usage.input_tokens
            usage["output_tokens"] += resp.usage.output_tokens
            usage["cached_tokens"] += resp.usage.cached_tokens

            if not resp.tool_calls:
                steps.append({"type": "final", "text": resp.text})
                result = {"answer": resp.text, "steps": steps, "iterations": i + 1, "usage": usage}
                break

            # Record the model's decision to call tools, then execute each and feed results back.
            messages.append(assistant(resp.text or None, resp.tool_calls))
            for call in resp.tool_calls:
                async with span(f"tool:{call.name}", "tool"):
                    tool_output = await dispatch_fn(call.name, call.args)
                steps.append({"type": "tool", "name": call.name, "args": call.args,
                              "result_preview": tool_output[:200]})
                messages.append(tool_result(call, tool_output))

        if result is None:
            result = {"answer": "(stopped: max iterations reached)", "steps": steps,
                      "iterations": max_iters, "usage": usage}

    result["trace_id"] = trace.id
    result["cost_usd"] = trace.total_cost_usd
    return result

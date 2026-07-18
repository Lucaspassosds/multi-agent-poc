"""The hand-rolled tool-use loop (topic: "orquestração sem framework").

No LangChain/CrewAI — just: call the model, if it asked for tools run them, feed the
results back, repeat until it produces a final answer (or we hit the iteration cap).
Every step is recorded for observability (Phase 6).
"""
from app.agents.tools import TOOL_SPECS, dispatch
from app.llm.base import Message, ToolSpec, assistant, tool_result, user
from app.llm.factory import get_provider


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

    for i in range(max_iters):
        resp = await provider.complete(
            model=model, system=system, messages=messages, tools=tools, max_tokens=1024
        )
        usage["input_tokens"] += resp.usage.input_tokens
        usage["output_tokens"] += resp.usage.output_tokens
        usage["cached_tokens"] += resp.usage.cached_tokens

        if not resp.tool_calls:
            steps.append({"type": "final", "text": resp.text})
            return {"answer": resp.text, "steps": steps, "iterations": i + 1, "usage": usage}

        # Record the model's decision to call tools, then execute each and feed results back.
        messages.append(assistant(resp.text or None, resp.tool_calls))
        for call in resp.tool_calls:
            result = await dispatch_fn(call.name, call.args)
            steps.append({"type": "tool", "name": call.name, "args": call.args,
                          "result_preview": result[:200]})
            messages.append(tool_result(call, result))

    return {"answer": "(stopped: max iterations reached)", "steps": steps,
            "iterations": max_iters, "usage": usage}

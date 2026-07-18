"""Gemini implementation of the neutral LLMProvider interface.

Translates our neutral Message/ToolSpec/ToolCall types <-> google-genai `types`.
Notes on Gemini specifics handled here:
- Content roles are only 'user' | 'model'. A tool *result* is sent as a 'user' turn
  containing a function_response part (not a special 'tool' role).
- We disable automatic function calling so WE run the tool loop (spec 04).
- usage_metadata.cached_content_token_count surfaces implicit-cache savings.
"""
from __future__ import annotations

from google import genai
from google.genai import types

from app.config import settings
from app.llm.base import LLMResponse, Message, ToolCall, ToolSpec, Usage
from app.llm.retry import with_retry


def _to_contents(messages: list[Message]) -> list[types.Content]:
    contents: list[types.Content] = []
    for m in messages:
        if m.role == "user":
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=m.content or "")]))
        elif m.role == "assistant":
            parts: list[types.Part] = []
            if m.content:
                parts.append(types.Part.from_text(text=m.content))
            for tc in m.tool_calls:
                # Re-send the ORIGINAL part when we have it — Gemini 3 requires the
                # thought_signature it carries; rebuilding from name/args would drop it.
                if tc.raw is not None:
                    parts.append(tc.raw)
                else:
                    parts.append(types.Part.from_function_call(name=tc.name, args=tc.args))
            contents.append(types.Content(role="model", parts=parts))
        elif m.role == "tool":
            # Gemini expects function responses back in a 'user' turn.
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=m.name or "", response={"result": m.content})],
            ))
    return contents


def _supports_thinking(model: str) -> bool:
    # Only 3.x / 2.5 / "-latest" (which alias to 3.x) accept thinking_config; 2.0 models error on it.
    m = model.lower()
    return "gemini-3" in m or "2.5" in m or m.endswith("-latest")


def _to_tool(tools: list[ToolSpec]) -> types.Tool:
    decls = [
        types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters)
        for t in tools
    ]
    return types.Tool(function_declarations=decls)


def _extract_text(resp) -> str:
    try:
        cand = (resp.candidates or [None])[0]
        if not cand or not cand.content or not cand.content.parts:
            return ""
        return "".join(p.text for p in cand.content.parts if getattr(p, "text", None))
    except Exception:
        return ""


def _to_response(resp) -> LLMResponse:
    # Iterate the candidate's parts (not resp.function_calls) so we can keep each
    # function_call's original Part — it carries Gemini 3's required thought_signature.
    calls: list[ToolCall] = []
    cand0 = (getattr(resp, "candidates", None) or [None])[0]
    if cand0 and cand0.content and cand0.content.parts:
        for i, part in enumerate(cand0.content.parts):
            fc = getattr(part, "function_call", None)
            if fc:
                calls.append(ToolCall(
                    id=getattr(fc, "id", None) or f"call_{i}",
                    name=fc.name, args=dict(fc.args or {}), raw=part,
                ))
    um = getattr(resp, "usage_metadata", None)
    usage = Usage(
        input_tokens=getattr(um, "prompt_token_count", 0) or 0,
        output_tokens=getattr(um, "candidates_token_count", 0) or 0,
        cached_tokens=getattr(um, "cached_content_token_count", 0) or 0,
    )
    cand = (getattr(resp, "candidates", None) or [None])[0]
    finish = str(getattr(cand, "finish_reason", None)) if cand else None
    return LLMResponse(text=_extract_text(resp), tool_calls=calls, usage=usage, finish_reason=finish, raw=resp)


class GeminiProvider:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def _config(self, system, tools, max_tokens, response_schema, thinking_budget=None) -> types.GenerateContentConfig:
        cfg = types.GenerateContentConfig(
            system_instruction=system or None,
            max_output_tokens=max_tokens,
        )
        if thinking_budget is not None:
            # thinking models (gemini 3.x) spend output tokens on reasoning; budget=0 disables it
            # so structured-JSON calls don't get truncated.
            cfg.thinking_config = types.ThinkingConfig(thinking_budget=thinking_budget)
        if tools:
            cfg.tools = [_to_tool(tools)]
            cfg.automatic_function_calling = types.AutomaticFunctionCallingConfig(disable=True)
        if response_schema is not None:
            cfg.response_mime_type = "application/json"
            cfg.response_schema = response_schema
        return cfg

    @with_retry()
    async def _generate(self, *, model, contents, config):
        return await self._client.aio.models.generate_content(model=model, contents=contents, config=config)

    async def complete(
        self, *, model, system, messages, tools=None, max_tokens=4096, cache=True,
        response_schema=None, thinking_budget=None,
    ) -> LLMResponse:
        # `cache` is a no-op hint for Gemini (implicit caching is automatic); it maps to
        # explicit cache_control when the Anthropic provider is added.
        tb = thinking_budget if _supports_thinking(model) else None
        resp = await self._generate(
            model=model,
            contents=_to_contents(messages),
            config=self._config(system, tools, max_tokens, response_schema, tb),
        )
        return _to_response(resp)

    async def stream(self, *, model, system, messages, max_tokens=4096):
        cfg = self._config(system, None, max_tokens, None)
        stream = await self._client.aio.models.generate_content_stream(
            model=model, contents=_to_contents(messages), config=cfg,
        )
        async for chunk in stream:
            text = _extract_text(chunk)
            if text:
                yield text

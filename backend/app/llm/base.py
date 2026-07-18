"""Provider-neutral LLM interface — the ONLY thing agent code imports.

Swapping Gemini <-> Claude is a config change (LLM_PROVIDER), not a code change,
because everything above this layer speaks these neutral types instead of a vendor SDK.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolSpec:
    """A tool the model may call, described by a JSON-schema parameter object."""
    name: str
    description: str
    parameters: dict


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict
    raw: Any = None   # opaque provider part (e.g. Gemini keeps thought_signature here) — re-sent verbatim


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0   # normalized across providers (Gemini implicit cache / Claude cache read)


@dataclass
class Message:
    """One conversation turn.

    - role="user":      content = user text
    - role="assistant": content = model text (optional) + tool_calls (optional)
    - role="tool":      a tool result — name + tool_call_id identify which call it answers
    """
    role: str
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    usage: Usage
    finish_reason: str | None = None
    raw: Any = None


# --- small constructors so agent code reads cleanly ---
def user(text: str) -> Message:
    return Message(role="user", content=text)


def assistant(text: str | None = None, tool_calls: list[ToolCall] | None = None) -> Message:
    return Message(role="assistant", content=text, tool_calls=tool_calls or [])


def tool_result(call: ToolCall, content: str) -> Message:
    return Message(role="tool", content=content, tool_call_id=call.id, name=call.name)


class LLMProvider(Protocol):
    async def complete(
        self,
        *,
        model: str,
        system: str | None,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 4096,
        cache: bool = True,
        response_schema: Any = None,
        thinking_budget: int | None = None,
    ) -> LLMResponse: ...

    def stream(
        self,
        *,
        model: str,
        system: str | None,
        messages: list[Message],
        max_tokens: int = 4096,
    ): ...

"""Phase 6 — a minimal, framework-free span tracer (topic: "observabilidade").

One `Trace` = one call to triage()/run_agent(). Nested `span(...)` calls attach as children via
contextvars, so instrumented code never threads a parent id by hand — and because each
`asyncio.gather()` task gets its own COPY of the current context, concurrent spans (the parallel
retrievers) each correctly parent under the same orchestrator span while their started_at/ended_at
timestamps genuinely overlap. Spans accumulate in memory and are written to Postgres in one shot
when the trace closes (Trace.__aexit__) — no live/streaming updates yet, that's Phase 8.
"""
# ── Concept: OBSERVABILITY ── framework-free Trace/span() via contextvars; nested + concurrent spans parent correctly; cost attribution.
import contextvars
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.db import get_pool
from app.llm.base import Usage
from app.llm.retry import last_attempts

_current_trace: contextvars.ContextVar = contextvars.ContextVar("current_trace", default=None)
_current_parent: contextvars.ContextVar = contextvars.ContextVar("current_parent", default=None)


def cost_usd(model: str | None, input_tokens: int, output_tokens: int) -> float:
    """List-price cost for a call. `settings.model_costs` is $/1M (input, output) tokens — this is
    what the provider would bill on a paid tier; Gemini's free tier actually bills $0."""
    rate_in, rate_out = settings.model_costs.get(model, settings.default_model_cost)
    return round(input_tokens / 1_000_000 * rate_in + output_tokens / 1_000_000 * rate_out, 6)


@dataclass
class SpanRecord:
    id: int
    parent_id: int | None
    name: str
    span_type: str
    model: str | None = None
    started_at: float = 0.0
    ended_at: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    retries: int = 0
    error: str | None = None

    def record_usage(self, usage: Usage) -> None:
        """Call right after the LLM response this span wraps comes back — folds in its token
        usage and (via last_attempts()) however many retries with_retry() just needed."""
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.cache_read_tokens += usage.cached_tokens
        self.retries += last_attempts()

    @property
    def cost(self) -> float:
        return cost_usd(self.model, self.input_tokens, self.output_tokens)


def _dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


class Trace:
    """`async with Trace("triage") as trace: ...` — opens a root span; persists everything on exit.

    Usable around any agent entrypoint (triage() or run_agent()); `trace.id` (the persisted
    Postgres id) is only valid AFTER the `async with` block exits.
    """

    def __init__(self, name: str, ticket_id: int | None = None):
        self.name = name
        self.ticket_id = ticket_id
        self.spans: list[SpanRecord] = []
        self.status = "ok"
        self.id: int | None = None
        self._next_id = 1
        self._root: SpanRecord | None = None
        self._trace_token = None
        self._parent_token = None

    def _new_span(self, name: str, span_type: str, model: str | None) -> SpanRecord:
        s = SpanRecord(id=self._next_id, parent_id=_current_parent.get(), name=name,
                        span_type=span_type, model=model)
        self._next_id += 1
        self.spans.append(s)
        return s

    async def __aenter__(self) -> "Trace":
        self._trace_token = _current_trace.set(self)
        self._root = self._new_span(self.name, "agent", None)
        self._root.started_at = time.time()
        self._parent_token = _current_parent.set(self._root.id)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._root.ended_at = time.time()
        if exc is not None:
            self.status = "error"
            self._root.error = str(exc)[:500]
        _current_parent.reset(self._parent_token)
        _current_trace.reset(self._trace_token)
        await self._persist()
        return False  # never swallow the exception

    @property
    def total_tokens(self) -> int:
        return sum(s.input_tokens + s.output_tokens for s in self.spans)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(s.cost for s in self.spans), 6)

    async def _persist(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn, conn.transaction():
            self.id = await conn.fetchval(
                """INSERT INTO traces (name, ticket_id, started_at, ended_at, status,
                                        total_tokens, total_cost_usd)
                   VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id""",
                self.name, self.ticket_id, _dt(self._root.started_at), _dt(self._root.ended_at),
                self.status, self.total_tokens, self.total_cost_usd,
            )
            id_map: dict[int, int] = {}
            for s in self.spans:
                parent_db_id = id_map.get(s.parent_id) if s.parent_id is not None else None
                db_id = await conn.fetchval(
                    """INSERT INTO spans (trace_id, parent_id, name, span_type, model,
                                           started_at, ended_at, input_tokens, output_tokens,
                                           cache_read_tokens, cache_creation_tokens, retries, error)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING id""",
                    self.id, parent_db_id, s.name, s.span_type, s.model,
                    _dt(s.started_at), _dt(s.ended_at or s.started_at),
                    s.input_tokens, s.output_tokens, s.cache_read_tokens, s.cache_creation_tokens,
                    s.retries, s.error,
                )
                id_map[s.id] = db_id


@asynccontextmanager
async def span(name: str, span_type: str = "subagent", model: str | None = None):
    """Open a child span under whatever Trace/span is currently active (via contextvars).

    Safe to use with no active Trace (e.g. standalone calls, tests): yields a throwaway,
    unpersisted record so instrumented code never needs an `if tracing:` branch.
    """
    trace = _current_trace.get()
    if trace is None:
        s = SpanRecord(id=-1, parent_id=None, name=name, span_type=span_type, model=model)
        s.started_at = time.time()
        try:
            yield s
        finally:
            s.ended_at = time.time()
        return

    s = trace._new_span(name, span_type, model)
    s.started_at = time.time()
    token = _current_parent.set(s.id)
    try:
        yield s
    except Exception as exc:
        s.error = str(exc)[:500]
        raise
    finally:
        s.ended_at = time.time()
        _current_parent.reset(token)

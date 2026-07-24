"""Langfuse Cloud wiring (Phase D) — a thin, provider-agnostic, disable-safe wrapper.

Everything Langfuse-specific lives here so the rest of the app imports neutral helpers that
no-op cleanly when keys are absent. This keeps observability.py and the LLM providers free of
vendor lock-in and lets the app boot without Langfuse credentials (important for the demo).
SDK v3 is OpenTelemetry-based; we instrument MANUALLY — no auto-patching of google-genai/anthropic.
"""
from __future__ import annotations

import contextlib
import logging
from typing import Any, Iterator

from app.config import settings

log = logging.getLogger("uvicorn.error")

_client: Any = None
enabled: bool = False


def init() -> None:
    """Build the singleton + verify auth once on startup. On ANY failure, log and stay disabled
    so the hand-rolled Postgres tracer keeps working and the app still boots."""
    global _client, enabled
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        log.info("Langfuse disabled (no keys) — hand-rolled Postgres tracing still active.")
        return
    try:
        from langfuse import Langfuse
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_base_url,
        )
        if _client.auth_check():
            enabled = True
            log.info("Langfuse auth OK — mirroring traces to %s", settings.langfuse_base_url)
        else:
            log.warning("Langfuse auth_check() failed — staying disabled.")
    except Exception as exc:  # noqa: BLE001 - never let telemetry break the request path
        log.warning("Langfuse init failed (%s) — staying disabled.", exc)


class _NoopObs:
    """Stand-in for a Langfuse span/generation when Langfuse is disabled."""

    def update(self, **_kw: Any) -> None: ...
    def update_trace(self, **_kw: Any) -> None: ...


@contextlib.contextmanager
def lf_span(name: str) -> Iterator[Any]:
    """A Langfuse span nested under the current OTel context (or a no-op)."""
    if not enabled:
        yield _NoopObs()
        return
    with _client.start_as_current_span(name=name) as s:
        yield s


@contextlib.contextmanager
def lf_generation(name: str, model: str | None, input_: Any = None) -> Iterator[Any]:
    """A Langfuse generation nested under the current span (or a no-op)."""
    if not enabled:
        yield _NoopObs()
        return
    with _client.start_as_current_generation(name=name, model=model, input=input_) as g:
        yield g


def set_trace_attributes(*, session_id: str | None = None, tags: list[str] | None = None,
                         name: str | None = None, output: Any = None) -> None:
    if not enabled:
        return
    _client.update_current_trace(session_id=session_id, tags=tags, name=name, output=output)


def current_trace_id() -> str | None:
    return _client.get_current_trace_id() if enabled else None


def current_trace_url() -> str | None:
    if not enabled:
        return None
    try:
        return _client.get_trace_url(trace_id=_client.get_current_trace_id())
    except Exception:  # noqa: BLE001 - method name is version-sensitive; verify in Step 6
        return None


def score(trace_id: str | None, name: str, value: float | str, comment: str | None = None) -> None:
    if not enabled or not trace_id:
        return
    try:
        _client.create_score(trace_id=trace_id, name=name, value=value, comment=comment)
    except Exception as exc:  # noqa: BLE001
        log.warning("Langfuse create_score(%s) failed: %s", name, exc)


def flush() -> None:
    if enabled:
        _client.flush()

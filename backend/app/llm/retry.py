"""Retry with exponential backoff + jitter.

Two failure classes:
- transient (429 rate-limit, 5xx, timeouts, connection drops) -> retry with growing delay
- permanent (4xx like 400/401/404) -> surface immediately, retrying wastes time and money

Gemini's free tier returns 429 under load, so this path is exercised for real.
"""
import asyncio
import contextvars
import functools
import random
import re

from google.genai import errors as genai_errors

_RETRYABLE_CODES = {408, 409, 429, 500, 502, 503, 504}
_RETRYABLE_EXC_NAMES = {"ConnectError", "ReadTimeout", "ConnectTimeout", "RemoteProtocolError", "TimeoutException", "ChaosError"}
_RETRY_DELAY_RE = re.compile(r"([\d.]+)")

# How many retries the most recently completed with_retry() call needed (0 = succeeded first try).
# Read by app/observability.py right after `await provider.complete(...)` returns, so a span can
# record retries without with_retry() needing to know about tracing.
_last_attempts: contextvars.ContextVar[int] = contextvars.ContextVar("last_attempts", default=0)


def last_attempts() -> int:
    return _last_attempts.get()


class ChaosError(Exception):
    """Synthetic transient failure injected by the chaos-toggle to exercise backoff on demand."""


# How many of the next with_retry()-wrapped attempts should raise a synthetic ChaosError before
# the real call runs. Set via set_chaos() at the top of a request so every subagent task
# (asyncio.create_task/gather copies the contextvars context) independently demos backoff.
_chaos_remaining: contextvars.ContextVar[int] = contextvars.ContextVar("chaos_remaining", default=0)


def set_chaos(n: int) -> None:
    _chaos_remaining.set(n)


def is_transient(exc: Exception) -> bool:
    if isinstance(exc, genai_errors.APIError):
        return getattr(exc, "code", None) in _RETRYABLE_CODES
    if isinstance(exc, asyncio.TimeoutError):
        return True
    return exc.__class__.__name__ in _RETRYABLE_EXC_NAMES


def _suggested_delay(exc: Exception) -> float | None:
    """Gemini's 429s carry a RetryInfo.retryDelay (e.g. "37s") telling us exactly how long its
    per-minute quota window needs — pure exponential backoff (capped at a few seconds) can't
    survive that, so honor the server's own number when it's given."""
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return None
    for d in details.get("error", {}).get("details", []):
        if str(d.get("@type", "")).endswith("RetryInfo") and "retryDelay" in d:
            match = _RETRY_DELAY_RE.match(d["retryDelay"])
            if match:
                return float(match.group(1))
    return None


# ── Concept: RETRY / BACKOFF ── exponential backoff + jitter on 429/5xx/timeouts; honors Gemini's RetryInfo.retryDelay.
def with_retry(max_attempts: int = 6, base_delay: float = 0.5, max_delay: float = 45.0):
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    remaining = _chaos_remaining.get()
                    if remaining > 0:
                        _chaos_remaining.set(remaining - 1)
                        raise ChaosError(f"injected 429 (chaos), {remaining} left")
                    result = await fn(*args, **kwargs)
                    _last_attempts.set(attempt)
                    return result
                except Exception as exc:
                    attempt += 1
                    if attempt >= max_attempts or not is_transient(exc):
                        raise
                    suggested = _suggested_delay(exc)
                    if suggested is not None:
                        # honor the server's advice + a little jitter so parallel callers that
                        # got rate-limited together don't all retry in the same instant
                        await asyncio.sleep(suggested + 1.0 + random.random() * 5)
                    else:
                        # exponential backoff with full jitter
                        delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                        await asyncio.sleep(delay * (0.5 + random.random()))
        return wrapper
    return decorator

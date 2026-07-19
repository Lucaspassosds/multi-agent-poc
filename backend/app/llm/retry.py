"""Retry with exponential backoff + jitter (topic: "resolver retry").

Two failure classes:
- transient (429 rate-limit, 5xx, timeouts, connection drops) -> retry with growing delay
- permanent (4xx like 400/401/404) -> surface immediately, retrying wastes time and money

Gemini's free tier returns 429 under load, so this path is exercised for real.
"""
import asyncio
import contextvars
import functools
import random

from google.genai import errors as genai_errors

_RETRYABLE_CODES = {408, 409, 429, 500, 502, 503, 504}
_RETRYABLE_EXC_NAMES = {"ConnectError", "ReadTimeout", "ConnectTimeout", "RemoteProtocolError", "TimeoutException"}

# How many retries the most recently completed with_retry() call needed (0 = succeeded first try).
# Read by app/observability.py right after `await provider.complete(...)` returns, so a span can
# record retries without with_retry() needing to know about tracing.
_last_attempts: contextvars.ContextVar[int] = contextvars.ContextVar("last_attempts", default=0)


def last_attempts() -> int:
    return _last_attempts.get()


def is_transient(exc: Exception) -> bool:
    if isinstance(exc, genai_errors.APIError):
        return getattr(exc, "code", None) in _RETRYABLE_CODES
    if isinstance(exc, asyncio.TimeoutError):
        return True
    return exc.__class__.__name__ in _RETRYABLE_EXC_NAMES


def with_retry(max_attempts: int = 4, base_delay: float = 0.5, max_delay: float = 8.0):
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    result = await fn(*args, **kwargs)
                    _last_attempts.set(attempt)
                    return result
                except Exception as exc:
                    attempt += 1
                    if attempt >= max_attempts or not is_transient(exc):
                        raise
                    # exponential backoff with full jitter
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    await asyncio.sleep(delay * (0.5 + random.random()))
        return wrapper
    return decorator

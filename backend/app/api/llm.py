"""Phase 2 demo endpoints — prove the LLM layer: chat, streaming, retry, caching, structured output.

All of these go through the provider-neutral interface, so they work unchanged when
LLM_PROVIDER flips to anthropic.
"""
import json
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.llm.base import user
from app.llm.factory import get_provider
from app.llm.retry import with_retry

router = APIRouter(prefix="/llm", tags=["llm"])


class ChatIn(BaseModel):
    message: str


@router.post("/chat")
async def chat(body: ChatIn):
    provider = get_provider()
    resp = await provider.complete(
        model=settings.model_resolve,
        system="You are a concise support assistant.",
        messages=[user(body.message)],
        max_tokens=512,
    )
    return {"text": resp.text, "usage": resp.usage.__dict__, "finish_reason": resp.finish_reason}


@router.get("/stream")
async def stream(q: str):
    provider = get_provider()

    async def gen():
        async for token in provider.stream(
            model=settings.model_resolve,
            system="You are a concise support assistant.",
            messages=[user(q)],
            max_tokens=512,
        ):
            yield f"data: {json.dumps(token)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/retry-demo")
async def retry_demo():
    """A flaky call that fails transiently twice, then succeeds — proving backoff recovery."""
    state = {"attempts": 0}

    class ReadTimeout(Exception):  # name is in retry's transient set
        pass

    @with_retry(max_attempts=5, base_delay=0.2)
    async def flaky():
        state["attempts"] += 1
        if state["attempts"] < 3:
            raise ReadTimeout("simulated transient failure")
        return "succeeded"

    t0 = time.time()
    result = await flaky()
    return {"result": result, "attempts": state["attempts"], "seconds": round(time.time() - t0, 3)}


# A deliberately large, stable prefix to trigger Gemini's implicit context cache on repeat.
_BIG_CONTEXT = (
    "You are a payments support assistant. Follow this policy manual exactly.\n"
    + ("Refunds return to the original payment method in 5-10 business days. "
       "Never refund a pending authorization; it drops off within 7 business days. "
       "Chargebacks cannot be double-refunded. Subscriptions are refundable within 14 days of renewal. ") * 60
)


@router.post("/cache-demo")
async def cache_demo():
    """Two identical large-prefix calls; the second should report cached tokens > 0."""
    provider = get_provider()
    out = []
    for _ in range(2):
        resp = await provider.complete(
            model=settings.model_resolve,
            system=_BIG_CONTEXT,
            messages=[user("In one sentence, when does a refund arrive?")],
            max_tokens=64,
        )
        out.append(resp.usage.__dict__)
    hit = out[1]["cached_tokens"] > 0
    return {
        "call_1": out[0],
        "call_2": out[1],
        "cache_hit_on_second": hit,
        "note": None if hit else (
            "No cache hit: the Gemini FREE tier gates prompt caching (implicit off; explicit storage "
            "quota exhausted). The interface already normalizes cached_tokens across providers, so this "
            "becomes a deterministic hit once LLM_PROVIDER=anthropic (cache_control) or on a paid tier."
        ),
    }


class TicketClass(BaseModel):
    category: str
    priority: str
    sentiment: str


@router.post("/classify-demo")
async def classify_demo(body: ChatIn):
    """Structured output: the model is constrained to the TicketClass schema (valid JSON)."""
    provider = get_provider()
    resp = await provider.complete(
        model=settings.model_classify,
        system="Classify the support ticket. category in {billing,refund,subscription,payment_failure,dispute,other}; "
               "priority in {low,medium,high}; sentiment in {angry,neutral,happy}.",
        messages=[user(body.message)],
        max_tokens=200,
        response_schema=TicketClass,
    )
    return {"raw_json": resp.text, "parsed": json.loads(resp.text) if resp.text else None,
            "usage": resp.usage.__dict__}

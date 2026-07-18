# 03 — LLM integration: provider abstraction, retry, caching (Phase 2)

> **Status note (2026-07-18):** Anthropic credits are temporarily blocked, so we build against
> **Google Gemini (free tier)** now and swap to **Claude** by changing one env var once credits work.
> The whole point of this phase is a **provider-agnostic `LLMProvider` interface** — ~11 of the 13 required
> concepts are provider-independent. Claude stays the *target* (topic: "aprender a usar api do Claude"),
> reached via a clean migration, not a rewrite.

## Purpose
A thin, well-understood layer over whatever LLM backend we use: streaming chat, tool-use, robust retry,
context/prompt caching, and structured outputs — all behind one interface the agents build on.

## Provider selection
- `.env`: `LLM_PROVIDER=gemini` (now) → `LLM_PROVIDER=anthropic` (once credits work).
- The agent/orchestrator code (Phases 3–7) imports the interface, **never** a concrete SDK.

## API key setup

### A) Gemini (do this now — free, no credit card)
1. Go to **aistudio.google.com** → sign in with any Google account.
2. Click **"Get API key"** → **Create API key** (no billing/card required for the free tier).
3. Copy it into `.env`: `GEMINI_API_KEY=...` (already git-ignored).
4. 🎓 Free tier has **rate limits** (requests/min + requests/day). That's fine — our retry layer treats
   429s as transient, and it makes the retry demo *authentic* instead of contrived.

### B) Anthropic (deferred until credits unblock)
1. **console.anthropic.com** → Settings → Billing → add payment method, buy credits (min $5).
2. Settings → API Keys → **Create Key** (shown once) → `.env`: `ANTHROPIC_API_KEY=sk-ant-...`.
3. Then set `LLM_PROVIDER=anthropic` and re-run — no code changes.

## Models (per role, per provider)
Roles keep cost matched to task difficulty; only the model IDs differ by provider.

| Role | Gemini (now) | Claude (later) | Why |
|---|---|---|---|
| Classifier | `gemini-flash-lite-latest` | `claude-haiku-4-5` | Cheap, fast |
| Retriever + Resolver | `gemini-flash-lite-latest` | `claude-sonnet-5` | Reliable free quota (see note) |
| Critic (LLM-as-judge) | `gemini-flash-lite-latest` | `claude-opus-4-8` | Reliable free quota (see note) |

> ⚠️ **Free-tier model reality (verified 2026-07) — why all three roles use flash-lite:**
> `gemini-2.5-*` are gated off for new keys; `gemini-flash-latest`/`gemini-3.5-flash` cap at **20 requests/day**;
> `gemini-pro-latest` returns 429; `gemini-2.0-flash` has **limit 0** (paid-only). Only **`gemini-flash-lite-latest`**
> has generous free quota, so on Gemini we consolidate all roles onto it. The multi-agent design (distinct
> role prompts) is unchanged; the haiku/sonnet/opus cost-tiering returns automatically at the Claude swap.

All IDs live in `.env` so we can retune. 🎓 The tiering itself is a talking point: match model cost to task difficulty.

## Provider interface contract
```python
# app/llm/base.py  — the ONLY thing agent code imports
@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    cached_tokens: int          # normalized across providers

@dataclass
class ToolCall:
    id: str; name: str; args: dict

@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    usage: Usage
    raw: object                 # provider-native object, for debugging

class LLMProvider(Protocol):
    async def complete(self, *, model, system, messages, tools=None,
                       max_tokens=4096, cache=True,
                       response_schema=None, stream=False) -> LLMResponse: ...
```
- **Async** everywhere (`client.aio` / `AsyncAnthropic`) — required for Phase 4 parallelism + FastAPI.
- Neutral tool spec (name/description/JSON-schema params) translated per provider inside each impl.
- Two impls: `app/llm/gemini.py` (`google-genai` SDK, `genai.Client`) and `app/llm/anthropic.py`
  (`anthropic.AsyncAnthropic`). A factory reads `LLM_PROVIDER`.

## Retry (topic: "resolver retry") — provider-agnostic
- **SDK built-ins** are layer one: `AsyncAnthropic(max_retries=4)`; `google-genai` retries transient errors too.
- **Our layer** (demonstrates understanding): a decorator around `complete()` + tool execution — exponential
  backoff + jitter, attempt caps, and `is_error` tool_results fed back so the model can adapt. Plus a
  forced-failure demo endpoint that injects a transient error and shows recovery.
- 🎓 Two failure classes: transient (429/5xx/timeout → retry) vs. permanent 4xx (surface, don't retry).
  Gemini free-tier 429s exercise this for real.

## Context / prompt caching (topic: "prompt caching")
Both providers can demo the concept; the interface hides the mechanism.
- **Gemini (now):** implicit caching exists for long repeated prefixes; explicit caching via
  `client.caches.create(...)`. ⚠️ **Verified: the FREE tier gates both** — implicit didn't trigger, and
  explicit `caches.create` returns 429 (storage quota ≈ 0) / requires ≥4096 tokens. So prompt caching is
  **not demonstrable on free Gemini**; the `/llm/cache-demo` endpoint reports this honestly. The interface
  still normalizes the metric (`Usage.cached_tokens`), so it's a deterministic hit once on Claude / paid tier.
- **Claude (later):** `cache_control: {"type":"ephemeral"}` on the last stable block (tools → system →
  large KB context), volatile ticket text *after* the breakpoint. Verify via `usage.cache_read_input_tokens`.
- We normalize both into `Usage.cached_tokens`, and the Phase 6 dashboard shows the savings live.
- ⚠️ Never interpolate timestamps/UUIDs into the cached prefix (silent invalidation) on either provider.
- 🎓 Cached reads are far cheaper; structure the prompt so the big stable stuff is the reusable prefix.

## Structured outputs (classifier, critic, evals)
- **Gemini:** `config={"response_mime_type":"application/json","response_schema": PydanticModel}`.
- **Claude:** `output_config={"format":{"type":"json_schema","schema":{...}}}` / `messages.parse()`.
- Interface exposes `response_schema=<PydanticModel>`; each impl maps it. Returns validated JSON.
- 🎓 Structured outputs replace fragile prompt-and-parse; the model is constrained to the schema.

## Claude-only bits (partial deferral)
- **Skills concept is demoable now**: the filesystem `SKILL.md` approach (spec 05, option a) is
  provider-agnostic — build it on Gemini. Only the native **Anthropic Agent Skills API** (option b) is
  Claude-only → defer until `LLM_PROVIDER=anthropic`. MCP (spec 05) is provider-agnostic too.
- The one genuine gap to call out in the demo: the native Agent Skills API and Anthropic `cache_control`
  exact metrics land after the Claude swap (Gemini's implicit cache still demonstrates the caching idea).

## Behavior / acceptance
- [ ] `GET /health` confirms the active provider's key works (cheap 1-token call).
- [ ] Swapping `LLM_PROVIDER` between `gemini`/`anthropic` needs **zero** code changes.
- [ ] Streaming demo endpoint relays tokens as SSE.
- [ ] Forced-error demo recovers via retry; logs show the attempts.
- [ ] Repeat call shows `cached_tokens > 0` (Gemini implicit cache or Claude cache read).
- [ ] Classifier returns schema-valid JSON on the active provider.

## Open questions
- Free-tier rate limits vs. Phase 4 parallelism: cap orchestrator concurrency (e.g. 3–4) and lean on the
  retry layer. Revisit if we hit daily caps during the demo.
- Hard per-run token ceiling for the orchestrator — deferred; revisit in Phase 4 if runs get expensive.

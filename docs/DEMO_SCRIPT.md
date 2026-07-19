# Demo talking track (~10-12 min)

A presenter outline, not a script to read verbatim — bullets are talking points, not sentences.
Pair with `docs/CONCEPTS.md` if the audience wants to go deeper on any one topic afterward.

## 0. Setup (before you're on screen)
- `docker compose up -d` already running; KB already ingested (persists in the `pgdata` volume,
  no need to re-run `/ingest`).
- Browser open to `http://localhost:5173` (Triage screen).
- Optional: `GET /evals` already has a `hybrid` run from a previous session, so you don't have to
  wait ~11 minutes live — see step 4.

## 1. Framing (30s)
- "A framework-free multi-agent system that triages support tickets and drafts a cited reply."
- One line on *why framework-free*: to actually show the mechanics — orchestration, context
  management, parallelism — instead of hiding them behind LangChain/CrewAI abstractions.
- Point at the architecture diagram in the README for 10 seconds, then go live.

## 2. Live demo — Triage screen (2-3 min)
- Submit the preset: *"I was charged twice for my subscription this month, please refund the
  duplicate."*
- Narrate the timeline **as it streams** (this is real, not simulated — see talking point below):
  - classify + plan run concurrently — point out both rows start together.
  - 2-3 retrievers fire **in parallel** — the overlapping rows *are* the parallelism, not a claim
    about it.
  - resolve → critique → (sometimes) one revision if the critic isn't satisfied.
- Final answer: point out the inline citations — click one, show the popover (title + source +
  snippet). Point out the classification chips (category/priority/sentiment).

## 3. Observability dashboard (2 min)
- Open Observability, click the trace that just ran.
- Waterfall = the same data you just watched live, persisted — same parallelism, now inspectable
  after the fact. Click a span to see its model/tokens/cost.
- Stat tiles: tokens, cost (list price), cache-hit % (0% today — Gemini free tier doesn't support
  caching; the field is real and will populate the moment this swaps to Claude), retries.

## 4. Evals (2 min)
- Show the latest run's aggregate scores: classification accuracy, retrieval hit-rate, citation
  coverage, faithfulness/helpfulness (LLM-as-judge).
- **The regression demo** (the credibility moment): switch retrieval mode to `lexical` and either
  re-run live or point at a `previous run` comparison already on screen — hit-rate and
  faithfulness collapse while classification accuracy stays flat, because classification doesn't
  depend on retrieval. This proves the eval harness actually measures something, not just green
  checkmarks.
- If short on time: skip the live re-run (mention it takes ~11 min on the free tier, see below)
  and just narrate the pre-computed numbers.

## 5. Engineering-judgment talking points (pick 2-3, ~1-2 min)
These are the "how I actually work" beats — more valuable to an EM than the UI itself.
- **Provider abstraction, forced by a real constraint**: Anthropic billing wasn't available, so
  the whole system runs on Gemini's free tier today behind a neutral `LLMProvider` interface —
  swapping to Claude is one env var + one new file, not a rewrite. ~11 of 13 required concepts are
  fully provider-agnostic already.
- **Found and root-caused a real bug at scale**: the golden-set eval sweep hit sustained 429s
  because Gemini's free tier caps at 15 req/min and one `triage()` call alone fires ~7-8 requests.
  Fixed the retry logic to parse the *server's own* `RetryInfo.retryDelay` instead of guessing a
  backoff — benefits every caller, not just evals.
- **Dropped a tool that didn't actually work**: `crawl4ai`'s headless browser was evaluated for
  ingest, but geo-localized Stripe's docs to the wrong language and hung behind a VPN. Swapped to
  a plain HTTP fetch, which just works. Simpler tool, better result — not every problem needs the
  fancier one.
- **Given an open architecture fork, chose the harder-but-more-honest option**: the spec called
  for a live streaming timeline, but the backend only had a synchronous endpoint. Rather than fake
  it with a client-side animation, refactored the orchestrator into a real event-emitting
  generator so the UI reflects genuine concurrent execution.

## 6. Close (30s)
- Recap the concept checklist coverage (point at `docs/CONCEPTS.md` for the full map).
- Invite questions — the codebase is small enough to open live and show the actual function
  behind any concept asked about.

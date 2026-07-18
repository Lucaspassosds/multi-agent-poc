# 07 — Evals (Phase 7)

## Purpose
Measure the pipeline's quality automatically, so we can prove it works and catch regressions.
(topic: "evals".)

## 🎓 Concepts
- **Deterministic metrics**: computed by code, no model — objective and free (accuracy, hit-rate, coverage).
- **LLM-as-judge**: a model grades open-ended quality (faithfulness, helpfulness) against a rubric —
  necessary where there's no single "correct" string. Use the top-tier model as the judge
  (`MODEL_CRITIC` — Gemini `pro` now / Claude `opus` later) and force a structured verdict.
- Combine both: cheap deterministic checks catch obvious failures; the judge scores the nuanced parts.

## Golden set
~20 tickets with expected labels + a reference answer:
```json
{
  "id": "g-001",
  "ticket": "I was charged twice for my subscription this month...",
  "expected_category": "billing/duplicate-charge",
  "expected_priority": "high",
  "reference_answer": "Acknowledge the duplicate charge, explain refund timeline, cite the refunds policy.",
  "must_cite": ["refunds", "subscription-billing"]
}
```
Stored as a fixture (`evals/golden.json`). Generated once, hand-checked.

## Metrics
| Metric | Type | How |
|---|---|---|
| Classification accuracy | deterministic | predicted category/priority == expected |
| Retrieval hit-rate | deterministic | did retrieved chunks include a `must_cite` source? |
| Citation coverage | deterministic | every claim in the draft maps to a retrieved citation |
| Answer faithfulness | LLM-judge | judge: is the answer grounded in the cited evidence? (0–1) |
| Answer helpfulness | LLM-judge | judge: does it resolve the ticket vs. the reference? (0–1) |

- LLM-judge returns a **structured** verdict (`output_config.format` / `messages.parse`): `{score, reasoning}`.

## API + flow
- `POST /evals/run` → runs the full triage pipeline over the golden set, scores each, stores results.
- `GET /evals` → latest run: per-metric aggregates + per-case breakdown.
- Reuses the observability spans so each eval case is also a trace (cost of an eval run is visible).

## Regression demo
- Deliberately break something (e.g. disable hybrid → lexical-only) and show hit-rate / faithfulness drop.
- 🎓 This is why evals matter: a change that "looks fine" is caught by the numbers.

## Behavior / acceptance
- [ ] `POST /evals/run` produces per-metric scores over the golden set.
- [ ] A deliberate regression measurably lowers the scores.
- [ ] React report screen (Phase 8) shows aggregates + drill-down.

## Open questions
- Judge model: top tier (quality) vs mid tier (cost) — `MODEL_CRITIC` vs `MODEL_RESOLVE`. Default top tier for the POC (Gemini `pro` now / Claude `opus` later); it's ~20 calls. Watch Gemini free-tier daily limits.

# 04 — Skills Rework (real library, 3-level disclosure, bundled code)

## Purpose
Turn Skills from a single markdown file into a proper **Agent-Skills-model** implementation: a small
skill *library*, full **three-level progressive disclosure**, **model-driven selection**, and at least
one **bundled executable script** — because "skills carry code" is the defining Agent-Skills feature,
and it's the thing the current POC most conspicuously lacks. Lands in `backend/app/skills/` (spec 01).

## Current state (why it reads as half-built)
- One skill (`policy-reply-formatter`), loaded by a **hardcoded** `load_skill(...)` call.
- Hand-rolled `---` frontmatter split; **two** disclosure levels, not three; **no** bundled scripts/assets.
- `list_skills()` is **dead code**; the docstring sells a "list-then-load" protocol that never runs
  (flagged in spec 02).

## Contract — the skill library (`app/skills/definitions/<name>/`)
| Skill | Level-2 body (loaded on relevance) | Level-3 bundled (loaded on demand) |
|---|---|---|
| `refund-policy` | refund/dispute decision tree, eligibility windows | `references/refund-matrix.md`; **`scripts/refund_eligibility.py`** (deterministic eligibility from ticket metadata) |
| `chargeback-dispute-builder` | dispute-evidence assembly steps | `references/dispute-evidence-fields.md`; `templates/evidence.md` |
| `dunning-retry-advisor` | failed-payment retry guidance | `references/decline-codes.md` |
| `policy-reply-formatter` *(existing)* | house style / tone / disclaimer / citation format | `references/tone-examples.md` |

### Three-level progressive disclosure (the current loader stops at 2)
1. **Level 1 — always in context:** only each skill's `name` + one-line `description` (YAML frontmatter).
2. **Level 2 — on relevance:** the `SKILL.md` body loads when the model/classifier selects the skill.
3. **Level 3 — on demand:** bundled `references/*`, `templates/*`, and **executable `scripts/*`** load
   (or run) only when the skill's body calls for them.

### Mechanics
- **Real YAML frontmatter** parser (replace the `---` string split), with an `allowed-tools`-style field
  declaring which tools a skill may use.
- **Model-driven selection**: expose `load_skill(name)` and `run_skill_script(name, script, args)` as
  tools (spec 05), or a classifier-driven pre-selection — the orchestrator no longer hardcodes one skill.
- **Bundled code proves skills carry logic**: `refund-policy/scripts/refund_eligibility.py` computes
  eligibility deterministically from ticket metadata and is invoked at level 3.
- Skills are also exposed over MCP as `skill://{name}` resources (spec 03).
- `list_skills()` becomes **live** (drives selection + the UI catalog), retiring the dead-code note in spec 02.

## 🎓 Teaching note
A **tool** is a function call; a **skill** is packaged expertise — instructions *plus optional code and
references* the model pulls in only when a task calls for it, without bloating the base prompt.
Three-level disclosure is the mechanism that keeps that expertise cheap until it's needed. A skill that
ships a runnable script is the clearest demonstration that skills are more than a prompt snippet.

## Acceptance
- [ ] ≥3 skills in `definitions/`, each with valid YAML frontmatter; `list_skills()` returns them.
- [ ] A ticket triggers **model/classifier-driven** selection of the right skill (not a hardcoded name).
- [ ] `refund_eligibility.py` runs at level 3 and its result visibly influences the resolution
      (e.g. trace badge: "`refund-policy` loaded; `refund_eligibility.py` → eligible=false").
- [ ] Level-1 context contains only names+descriptions (verify the base prompt isn't bloated with bodies).
- [ ] `skill://<name>` is readable over MCP (spec 03).

## Cross-refs & sequencing
- **Depends on spec 01 step 5** (loader → `skills/loader.py`, data → `skills/definitions/`, `_SKILLS_DIR`
  fix) — move first, land this rework in the new location.
- **Ties to spec 05**: `check_refund_eligibility` tool is backed by this skill's script (Tools ↔ Skills).
- **Feeds spec 08**: a Skills catalog panel showing disclosure levels + a per-run "skill loaded" badge.

## Open questions
- Selection: model-driven (a `load_skill` tool the resolver calls) vs classifier-driven (pre-select in
  the classify node)? Recommend **model-driven via a tool** — it demonstrates the on-demand story best.
- Anthropic **Agent Skills API** (`container.skills` + code-execution betas) is Claude-only → keep the
  filesystem implementation now; note the managed path as the post-Claude-swap upgrade.

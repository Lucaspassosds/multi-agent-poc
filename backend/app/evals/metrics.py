"""Deterministic evals metrics (topic: "evals") — cheap, objective, no model call involved.

Each operates on one golden-set case (`golden.json`) + the corresponding `orchestrator.triage()`
result dict. The LLM-as-judge (judge.py) covers what these can't: whether the *reply itself* is
grounded and helpful, not just whether the pipeline picked the right label/sources.
"""


def classification_match(case: dict, result: dict) -> tuple[bool, bool]:
    """(category_correct, priority_correct) against the golden case's expected labels."""
    classification = result["classification"]
    return (
        classification.get("category") == case["expected_category"],
        classification.get("priority") == case["expected_priority"],
    )


def retrieval_hit(case: dict, result: dict) -> bool:
    """Did retrieval surface at least one of the ticket's must_cite KB titles?"""
    must_cite = case.get("must_cite") or []
    if not must_cite:
        return True
    cited_titles = {c["title"] for e in result["evidence"] for c in e["cited"]}
    return bool(set(must_cite) & cited_titles)


def citation_coverage(result: dict) -> float:
    """Fraction of retrieved evidence titles that literally appear in the final reply.

    A deterministic proxy for "the draft's claims trace back to what was retrieved" — true
    claim-level attribution would need its own LLM call, which is what the judge's faithfulness
    score is for.
    """
    cited_titles = {c["title"] for e in result["evidence"] for c in e["cited"]}
    if not cited_titles:
        return 0.0
    reply = result["final_reply"].lower()
    hits = sum(1 for title in cited_titles if title.lower() in reply)
    return round(hits / len(cited_titles), 4)

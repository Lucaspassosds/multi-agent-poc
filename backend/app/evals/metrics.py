"""Deterministic evals metrics — cheap, objective, no model call involved.

Each operates on one golden-set case (`golden.json`) + the corresponding `orchestrator.triage()`
result dict. The LLM-as-judge (judge.py) covers what these can't: whether the *reply itself* is
grounded and helpful, not just whether the pipeline picked the right label/sources.
"""
# ── Concept: EVALS (deterministic metrics) ── cheap, objective, model-free scores over each golden-set case.


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


def classify_failures(case: dict, result: dict, verdict: dict,
                       faithfulness_floor: float = 0.6) -> list[str]:
    """Failure-taxonomy labels for one scored case (empty list = clean).

    - hallucinated_policy: judge faithfulness below the floor (invented/unsupported policy)
    - missed_citation:     retrieval missed a required KB title (retrieval_hit False)
    - wrong_category:      predicted category != expected
    - over_escalation:     escalated (priority high) when the case did not warrant it
    - under_escalation:    did not escalate when the case warranted it
    """
    labels: list[str] = []
    if verdict.get("faithfulness_score", 1.0) < faithfulness_floor:
        labels.append("hallucinated_policy")
    if not retrieval_hit(case, result):
        labels.append("missed_citation")
    cat_ok, _ = classification_match(case, result)
    if not cat_ok:
        labels.append("wrong_category")
    expected_esc = case.get("expected_escalation", case["expected_priority"] == "high")
    predicted_esc = result["classification"].get("priority") == "high"
    if predicted_esc and not expected_esc:
        labels.append("over_escalation")
    if expected_esc and not predicted_esc:
        labels.append("under_escalation")
    return labels

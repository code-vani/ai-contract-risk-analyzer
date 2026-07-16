"""
risk_ranker.py — Task 5

Sorts the combined risk list (contradictions + overrides + financial
flags) by severity and assigns sequential RISK-### IDs.

Sort order: BLOCKER, HIGH, MEDIUM, LOW, then anything unrecognized last
(BLOCKER is included even though Component 4 doesn't produce it itself,
because Component 5 merges its MISSING_DOCUMENT/BLOCKER risks back through
this same shape before sending to the frontend — safer to support it here
than to require every caller to remember not to pass it in).
"""

SEVERITY_ORDER = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
UNKNOWN_SEVERITY_RANK = 99


def rank_risks(risks: list[dict]) -> list[dict]:
    """
    Takes a list of risk dicts (any shape, as long as they have a
    'severity' key) and returns a new list, sorted by severity, each with
    a 'risk_id' field added (RISK-001, RISK-002, ...).

    Sorting is stable — risks of equal severity keep their relative order
    from the input list, so callers get deterministic output.

    Does not mutate the input list or dicts.
    """
    if not risks:
        return []

    def sort_key(risk: dict):
        severity = (risk or {}).get("severity", "")
        return SEVERITY_ORDER.get(severity, UNKNOWN_SEVERITY_RANK)

    sorted_risks = sorted(risks, key=sort_key)

    ranked = []
    for i, risk in enumerate(sorted_risks, start=1):
        risk_copy = dict(risk)  # don't mutate caller's dicts
        risk_copy["risk_id"] = f"RISK-{i:03d}"
        # Edge case: if severity was missing/unrecognized, don't silently
        # let it look like a normal LOW risk — mark it so a human notices.
        if risk_copy.get("severity") not in SEVERITY_ORDER:
            risk_copy["severity"] = risk_copy.get("severity") or "UNKNOWN"
        ranked.append(risk_copy)

    return ranked


if __name__ == "__main__":
    import json

    test_risks = [
        {"type": "FINANCIAL_CLAUSE", "severity": "MEDIUM", "description": "money stuff"},
        {"type": "CONTRADICTION", "severity": "HIGH", "description": "payment conflict"},
        {"type": "OVERRIDE", "severity": "HIGH", "description": "notwithstanding clause"},
        {"type": "MISSING_DOCUMENT", "severity": "BLOCKER", "description": "exhibit A missing"},
        {"type": "WEIRD", "severity": "URGENT", "description": "unrecognized severity"},  # edge case
    ]
    print(json.dumps(rank_risks(test_risks), indent=2))

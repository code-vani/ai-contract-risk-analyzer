"""Component 5, Task 4 — combine and sort the final analysis output.

Merges risks (with redlines attached) and missing-document refusals into one
list, sorted by severity so the most serious items surface first. This combined
list is what the frontend renders.
"""

# Lower number = higher priority. CRITICAL (from circular references) is treated
# just below BLOCKER. Unknown severities sort last.
_SEVERITY_RANK = {
    "BLOCKER": 0,
    "CRITICAL": 1,
    "HIGH": 2,
    "MEDIUM": 3,
    "LOW": 4,
}


def _rank(item: dict) -> int:
    return _SEVERITY_RANK.get(str(item.get("severity", "")).upper(), 99)


def format_output(risks_with_redlines: list[dict], missing_docs: list[dict]) -> list[dict]:
    """Return a single severity-sorted list of risks + missing-doc refusals.

    Order: BLOCKER > CRITICAL > HIGH > MEDIUM > LOW. Sort is stable, so items of
    equal severity keep their incoming order (e.g. RISK-001 before RISK-002).
    """
    combined = list(missing_docs) + list(risks_with_redlines)
    return sorted(combined, key=_rank)


def summarize(items: list[dict]) -> dict:
    """Count items by severity for the frontend's summary bar."""
    counts = {"blocker": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}
    for item in items:
        sev = str(item.get("severity", "")).lower()
        if sev in counts:
            counts[sev] += 1
    counts["total"] = len(items)
    return counts

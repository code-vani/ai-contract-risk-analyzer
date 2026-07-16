"""
financial_risk_detector.py — Task 3 + cross-document financial conflict detection

Two detectors live here:

  detect_financial_risks(clauses)
    Per-clause scan: flags clauses containing money amounts, percentages,
    or financial keywords. Severity MEDIUM — needs human review.
    Deliberately NOT "any digit present" — a clause like "delivery within
    30 days" has a number but is not financial. We require a monetary/
    percentage signal OR a financial keyword near a number to keep false
    positives low.

  detect_cross_document_financial_conflicts(clauses)
    Cross-document scan: finds cases where a SOW dollar amount exceeds an
    MSA liability/payment cap. This is a HIGH-severity risk that the per-
    clause detector misses because it only sees one clause at a time.
    Example: MSA caps liability at $100K, SOW specifies $250K milestone →
    enforcement gap that could expose a party to uncapped liability.
"""

import re

# ── Per-clause patterns ───────────────────────────────────────────────────────

MONEY_PATTERN = re.compile(
    r"(\$\s?[\d,]+(?:\.\d{2})?)|(USD\s?[\d,]+)|([\d,]+(?:\.\d{2})?\s?(?:USD|dollars))",
    re.IGNORECASE,
)

PERCENT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s?%")

FINANCIAL_KEYWORD_PATTERN = re.compile(
    r"\b(fee|fees|penalty|penalties|liquidated damages|late fee|interest rate|"
    r"milestone payment|service level|SLA|cap(?:ped)?|indemnif\w*|invoice|"
    r"chargeback|refund|discount|surcharge)\b",
    re.IGNORECASE,
)

# A financial keyword only "counts" as a real signal if there's also a
# number reasonably nearby — otherwise "cap" in "capital city" style false
# positives could sneak through on generic legal boilerplate.
NUMBER_PATTERN = re.compile(r"\d")


def _classify_signals(text: str) -> dict:
    money_matches = MONEY_PATTERN.findall(text)
    money_found = any(any(g) for g in money_matches) if money_matches else False
    percent_found = bool(PERCENT_PATTERN.search(text))
    keyword_matches = FINANCIAL_KEYWORD_PATTERN.findall(text)
    keyword_found = bool(keyword_matches) and bool(NUMBER_PATTERN.search(text))

    return {
        "money": money_found,
        "percent": percent_found,
        "keyword": keyword_found,
        "keywords_matched": list(set(m for m in keyword_matches if m)),
    }


def detect_financial_risks(clauses: list[dict]) -> list[dict]:
    """
    Returns a list of FINANCIAL_CLAUSE risk objects (severity MEDIUM) for
    clauses containing monetary amounts, percentages, or financial
    keywords paired with a number (fees, penalties, SLAs, caps, etc).

    Empty/missing text is skipped safely.
    """
    if not clauses:
        return []

    flagged = []

    for clause in clauses:
        text = (clause or {}).get("text", "") or ""
        section = (clause or {}).get("section_number", "UNKNOWN")
        doc_type = (clause or {}).get("document_type", "UNKNOWN")

        if not text.strip():
            continue

        signals = _classify_signals(text)

        if not (signals["money"] or signals["percent"] or signals["keyword"]):
            continue

        reasons = []
        if signals["money"]:
            reasons.append("monetary amount")
        if signals["percent"]:
            reasons.append("percentage")
        if signals["keyword"]:
            kw = ", ".join(signals["keywords_matched"][:3]) if signals["keywords_matched"] else "financial term"
            reasons.append(f"financial keyword ({kw})")

        flagged.append({
            "type": "FINANCIAL_CLAUSE",
            "severity": "MEDIUM",
            "clause_section": section,
            "document_type": doc_type,
            "clause_text": text,
            "description": (
                f"{doc_type} § {section} contains {', '.join(reasons)} — "
                f"flagged for extra human review of exact figures."
            ),
        })

    return flagged


# ── Cross-document financial conflict detection ───────────────────────────────

# Language that signals a liability/payment cap in an MSA clause.
_CAP_LANGUAGE_PATTERN = re.compile(
    r"\b(?:cap(?:ped)?(?:\s+at)?|not\s+(?:to\s+)?exceed|maximum"
    r"(?:\s+(?:aggregate\s+)?(?:of|liability))?|limit(?:ed)?(?:\s+to)?|ceiling)\b",
    re.IGNORECASE,
)

# Extracts dollar amounts from text as floats (handles $1,000,000 and 1000000 USD).
_DOLLAR_AMOUNT_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d{0,2})?)"
    r"|([\d,]+(?:\.\d{0,2})?)\s*(?:USD|dollars)\b",
    re.IGNORECASE,
)


def _extract_dollar_amounts(text: str) -> list[float]:
    amounts = []
    for match in _DOLLAR_AMOUNT_RE.finditer(text):
        raw = match.group(1) or match.group(2)
        try:
            amounts.append(float(raw.replace(",", "")))
        except ValueError:
            pass
    return amounts


def detect_cross_document_financial_conflicts(clauses: list[dict]) -> list[dict]:
    """
    Compares dollar amounts across MSA and SOW to surface cases where a
    SOW amount exceeds an MSA cap — a high-impact risk invisible to per-
    clause analysis.

    Algorithm:
      1. Collect every MSA clause that contains cap language + a dollar amount.
      2. Collect every SOW dollar amount.
      3. Flag each (MSA cap section, SOW section) pair where the SOW amount
         exceeds the MSA cap by more than 10% (buffer prevents noise on
         near-equal values that may represent the same figure).

    Returns HIGH severity FINANCIAL_CLAUSE risks with msa_cap_section,
    msa_cap_amount, sow_amount, and which_wins fields — ready for
    normalize_risks() to map into graph node IDs.
    """
    if not clauses:
        return []

    msa_caps: list[dict] = []
    sow_financials: list[dict] = []

    for clause in clauses:
        text = (clause or {}).get("text", "") or ""
        doc_type = (clause or {}).get("document_type", "")
        section = (clause or {}).get("section_number", "UNKNOWN")

        if not text.strip():
            continue

        if doc_type == "MSA" and _CAP_LANGUAGE_PATTERN.search(text):
            for amount in _extract_dollar_amounts(text):
                msa_caps.append({"amount": amount, "section": section, "text": text[:300]})

        elif doc_type == "SOW":
            for amount in _extract_dollar_amounts(text):
                sow_financials.append({"amount": amount, "section": section, "text": text[:300]})

    if not msa_caps or not sow_financials:
        return []

    conflicts = []
    seen_pairs: set[tuple] = set()

    for cap in msa_caps:
        for sow in sow_financials:
            pair_key = (cap["section"], sow["section"])
            if pair_key in seen_pairs:
                continue
            if sow["amount"] > cap["amount"] * 1.1:
                seen_pairs.add(pair_key)
                conflicts.append({
                    "type": "FINANCIAL_CLAUSE",
                    "severity": "HIGH",
                    "clause_section": sow["section"],
                    "document_type": "SOW",
                    "msa_cap_section": cap["section"],
                    "msa_cap_amount": cap["amount"],
                    "sow_amount": sow["amount"],
                    "description": (
                        f"Cross-document financial conflict: SOW § {sow['section']} specifies "
                        f"${sow['amount']:,.0f} which exceeds the MSA § {cap['section']} cap of "
                        f"${cap['amount']:,.0f}. This creates a potential enforcement gap."
                    ),
                    "which_wins": (
                        f"MSA § {cap['section']}'s cap of ${cap['amount']:,.0f} would likely prevail "
                        f"absent explicit override language in SOW § {sow['section']}. "
                        f"Legal review required to confirm whether the SOW amount is intended "
                        f"to supersede the MSA cap."
                    ),
                })

    return conflicts


if __name__ == "__main__":
    import json

    test_clauses = [
        {"section_number": "4.1", "document_type": "MSA", "text": "Late payments incur a 1.5% monthly interest rate."},
        {"section_number": "6", "document_type": "SOW", "text": "Total contract value is $250,000 USD."},
        {"section_number": "2", "document_type": "MSA", "text": "Delivery shall occur within 30 days of signing."},  # should NOT flag
        {"section_number": "9", "document_type": "SOW", "text": ""},  # empty edge case
    ]
    print("--- Per-clause flags ---")
    print(json.dumps(detect_financial_risks(test_clauses), indent=2))

    cross_test = [
        {"section_number": "4", "document_type": "MSA",
         "text": "Aggregate liability shall not exceed $100,000 under any circumstances."},
        {"section_number": "9", "document_type": "SOW",
         "text": "Total milestone payment upon delivery: $250,000."},
    ]
    print("\n--- Cross-document conflicts ---")
    print(json.dumps(detect_cross_document_financial_conflicts(cross_test), indent=2))

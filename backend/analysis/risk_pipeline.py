"""
risk_pipeline.py

The .md spec's "Outputs" section for Component 4 describes ONE combined,
ranked JSON array covering contradictions, overrides, and financial flags
together. The individual detector files each do their own piece (Tasks
1-3), but nothing was combining + normalizing + ranking them into that
single output (Tasks 4-5 exist for contradictions only). This file is
that missing piece — it's what Component 6 (FastAPI) should actually call.

Also fixes a real integration problem: contradiction/override/financial
risks currently come back in three different shapes (different field
names for "which clause", no confidence on override/financial risks).
Component 5 (redline generator) needs one predictable shape to pull
"original_text" from regardless of risk type — normalize_risks() does that.
"""
import time
import logging

try:
    # Package-style import — used when Component 6 does
    # `from analysis import run_risk_detection`
    from .contradiction_detector import detect_all_contradictions
    from .override_detector import detect_overrides
    from .financial_risk_detector import detect_financial_risks, detect_cross_document_financial_conflicts
    from .risk_ranker import rank_risks
except ImportError:
    # Flat import — used when running this file directly for local testing
    # (`python risk_pipeline.py`) or from inside pytest run from this folder
    from contradiction_detector import detect_all_contradictions
    from override_detector import detect_overrides
    from financial_risk_detector import detect_financial_risks, detect_cross_document_financial_conflicts
    from risk_ranker import rank_risks

logger = logging.getLogger(__name__)


def normalize_risks(risks: list[dict]) -> list[dict]:
    """
    Ensures every risk object — regardless of which detector produced it —
    has "confidence" and "original_text" fields, so downstream code
    (Component 5's redline generator) never has to special-case on `type`
    just to find the clause text.

    Also fills in the flat RiskObject fields the breakdown doc's schema
    promises to Components 5/6/9 (clause_a_section, clause_b_section,
    suggested_text, change_summary) — each detector here returns its own
    richer/nested shape (e.g. CONTRADICTION keeps full clause_a/clause_b
    dicts, OVERRIDE keeps overriding_clause_section/overridden_section),
    which is kept as-is; this just adds the flat aliases on top so a
    caller written against the documented schema doesn't KeyError. Fields
    Component 4 has no way to know yet (suggested_text, change_summary —
    those are Component 5's job) are filled with None rather than omitted,
    so downstream code can rely on the key always being present.

    Does not mutate input. Safe to call twice (idempotent).
    """
    normalized = []
    for risk in risks:
        r = dict(risk)
        risk_type = r.get("type")

        if r.get("confidence") is None:
            # Override/financial risks are deterministic regex matches, not
            # AI guesses — there's no meaningful "uncertainty" to report,
            # so 1.0 is correct here, not a placeholder.
            r["confidence"] = 1.0

        if "original_text" not in r:
            if risk_type == "CONTRADICTION":
                # Redline the SOW side by default — it's typically the
                # negotiated document; Component 5 can override this choice.
                r["original_text"] = (r.get("clause_b") or {}).get("text", "")
            elif risk_type == "OVERRIDE":
                # Use the full clause text; fall back to the short snippet.
                r["original_text"] = r.get("clause_text") or r.get("matched_text") or r.get("description", "")
            else:  # FINANCIAL_CLAUSE or anything else
                # Use the actual clause text, not the flag description.
                r["original_text"] = r.get("clause_text") or r.get("description", "")

        if "clause_a_section" not in r or "clause_b_section" not in r:
            if risk_type == "CONTRADICTION":
                # Build node IDs in the format graph_serializer expects: "MSA-4.1"
                ca = r.get("clause_a") or {}
                cb = r.get("clause_b") or {}
                ca_doc = ca.get("document_type", "")
                cb_doc = cb.get("document_type", "")
                ca_sec = ca.get("section", "")
                cb_sec = cb.get("section", "")
                r.setdefault("clause_a_section",
                             f"{ca_doc}-{ca_sec}" if ca_doc and ca_sec else ca_sec or None)
                r.setdefault("clause_b_section",
                             f"{cb_doc}-{cb_sec}" if cb_doc and cb_sec else cb_sec or None)
            elif risk_type == "OVERRIDE":
                # overriding_document_type + overriding_clause_section → "SOW-7"
                ov_doc = r.get("overriding_document_type", "")
                ov_sec = r.get("overriding_clause_section", "")
                r.setdefault("clause_a_section",
                             f"{ov_doc}-{ov_sec}" if ov_doc and ov_sec else ov_sec or None)
                r.setdefault("clause_b_section", r.get("overridden_section"))
            elif risk_type == "FINANCIAL_CLAUSE":
                doc = r.get("document_type", "")
                sec = r.get("clause_section", "")
                r.setdefault("clause_a_section",
                             f"{doc}-{sec}" if doc and sec else sec or None)
                # Cross-document conflicts carry msa_cap_section so the graph
                # can draw an edge between the two nodes (SOW clause → MSA cap).
                msa_cap_sec = r.get("msa_cap_section")
                r.setdefault("clause_b_section",
                             f"MSA-{msa_cap_sec}" if msa_cap_sec else None)
            else:
                r.setdefault("clause_a_section", None)
                r.setdefault("clause_b_section", None)

        # Component 5 (redline generator) fills these in later — reserve
        # the keys now so callers following the documented RiskObject
        # shape can rely on them existing, even before a redline runs.
        r.setdefault("suggested_text", None)
        r.setdefault("change_summary", None)

        normalized.append(r)
    return normalized


def run_risk_detection(
    clause_pairs: list[dict],
    all_clauses: list[dict],
    delay_seconds: float = 0.5,
    _call_fn=None,
) -> list[dict]:
    """
    The single entrypoint Component 6 should call.

    Args:
        clause_pairs: [{ "clause_a": {...}, "clause_b": {...} }, ...] — same-topic
                      MSA/SOW pairs from Component 3's find_topic_pairs()
        all_clauses:  full flat list of every clause (MSA + SOW combined) —
                      needed by override/financial detectors, which scan every
                      clause, not just paired ones
        delay_seconds: Task 4's required rate-limit delay between Gemini calls
        _call_fn: optional injectable Gemini caller, for testing without a
                  real API key/network (passed straight through to
                  detect_all_contradictions)

    Returns:
        Final ranked, ID-assigned, shape-normalized risk list — ready to
        hand to Component 5 (redlines) or send straight to the frontend.

    Never raises: a failure in any one detector is logged and treated as
    "that detector found nothing" rather than aborting the whole analysis.
    """
    risks: list[dict] = []

    try:
        kwargs = {"delay_seconds": delay_seconds}
        if _call_fn is not None:
            kwargs["_call_fn"] = _call_fn
        risks += detect_all_contradictions(clause_pairs, **kwargs)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Contradiction detection failed entirely: {e}")

    try:
        risks += detect_overrides(all_clauses)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Override detection failed entirely: {e}")

    try:
        risks += detect_financial_risks(all_clauses)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Financial risk detection failed entirely: {e}")

    try:
        risks += detect_cross_document_financial_conflicts(all_clauses)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Cross-document financial conflict detection failed entirely: {e}")

    risks = normalize_risks(risks)
    return rank_risks(risks)


if __name__ == "__main__":
    import json

    def fake_gemini(prompt: str) -> str:
        return json.dumps({
            "is_contradiction": True,
            "severity": "HIGH",
            "description": "SOW allows 45 days; MSA requires 30 days.",
            "which_wins": "MSA governs unless overridden.",
            "confidence": 0.95,
        })

    pairs = [{
        "clause_a": {"section_number": "MSA-4.1", "text": "Payment due within thirty (30) days."},
        "clause_b": {"section_number": "SOW-2.3", "text": "Payment due within forty-five (45) days."},
    }]
    clauses = [
        {"section_number": "9", "document_type": "SOW",
         "text": "Notwithstanding MSA Section 7, liability is uncapped."},
        {"section_number": "6", "document_type": "MSA",
         "text": "Late fee of 1.5% applies, capped at $500."},
    ]

    final = run_risk_detection(pairs, clauses, delay_seconds=0, _call_fn=fake_gemini)
    print(json.dumps(final, indent=2))

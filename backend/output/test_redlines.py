"""Standalone tests for Component 5 (no server, no teammate components).

Run from the backend/ directory:
    python -m output.test_redlines

Uses the real Gemini API when GEMINI_API_KEY is set, otherwise the deterministic
mock in ai/redline_client.py — either way these assertions hold.
"""

from output.missing_doc_detector import find_missing_documents
from output.output_formatter import format_output, summarize
from output.redline_generator import generate_redline, generate_redlines


def test_generate_redline_payment():
    result = generate_redline(
        original_text="All milestone payments are due within forty-five (45) days of invoice.",
        risk_description="Payment term conflict: SOW 45 days vs MSA 30 days.",
        suggested_change="Change 45 days to 30 days to align with MSA Section 4.1.",
    )
    assert set(result) >= {
        "suggested_text",
        "change_summary",
        "words_removed",
        "words_added",
        "change_type",
    }
    assert "30" in result["suggested_text"], result["suggested_text"]
    print("PASS  generate_redline -> ", result["suggested_text"])


def test_generate_redlines_severity_handling():
    risks = [
        {"risk_id": "R1", "severity": "HIGH", "description": "d",
         "original_text": "terminate with seven (7) days notice"},
        {"risk_id": "R2", "severity": "LOW", "description": "d",
         "original_text": "minor stylistic issue"},
    ]
    enriched = generate_redlines(risks)
    assert enriched[0]["redline"] is not None
    assert enriched[1]["redline"] is None
    assert enriched[1]["change_summary"] == "Review recommended"
    print("PASS  generate_redlines severity handling")


def test_find_missing_documents():
    clauses = [
        {
            "section_number": "3.1",
            "document_type": "SOW",
            "text": "Deliverables are as specified in Schedule 1 - Project Scope Document.",
        },
        {
            "section_number": "7",
            "document_type": "SOW",
            "text": "Pricing shall be as per Exhibit A.",
        },
    ]
    refusals = find_missing_documents(clauses, ["MSA.pdf", "SOW.pdf"])
    assert len(refusals) == 2, refusals
    assert all(r["severity"] == "BLOCKER" for r in refusals)
    kinds = {r["referenced_document"] for r in refusals}
    assert any("Schedule 1" in k for k in kinds), kinds
    assert any("Exhibit A" in k for k in kinds), kinds
    print("PASS  find_missing_documents -> ", sorted(kinds))


def test_find_missing_documents_present_is_skipped():
    clauses = [{
        "section_number": "3.1", "document_type": "SOW",
        "text": "See Schedule 1 for details.",
    }]
    refusals = find_missing_documents(clauses, ["MSA.pdf", "SOW.pdf", "Schedule_1.pdf"])
    assert refusals == [], refusals
    print("PASS  provided document is not flagged")


def test_format_output_ordering():
    risks = [
        {"risk_id": "R1", "severity": "HIGH", "type": "CONTRADICTION"},
        {"risk_id": "R2", "severity": "LOW", "type": "FINANCIAL_CLAUSE"},
    ]
    missing = [{"type": "MISSING_DOCUMENT", "severity": "BLOCKER"}]
    ordered = format_output(risks, missing)
    assert ordered[0]["severity"] == "BLOCKER"
    assert ordered[-1]["severity"] == "LOW"
    counts = summarize(ordered)
    assert counts["total"] == 3 and counts["blocker"] == 1 and counts["high"] == 1
    print("PASS  format_output ordering + summary")


if __name__ == "__main__":
    test_generate_redline_payment()
    test_generate_redlines_severity_handling()
    test_find_missing_documents()
    test_find_missing_documents_present_is_skipped()
    test_format_output_ordering()
    print("\nAll Component 5 tests passed.")

"""Quick smoke test for Component 5 & 6 — no server, no Gemini API needed.

Run from backend/:
    python test_c5_c6.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Force UTF-8 output on Windows so special chars don't crash the console.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("=" * 60)
print("Component 5 & 6 Smoke Test")
print("=" * 60)

# ── Test 1: Missing Document Detector ────────────────────────────────────────
print("\n[1] missing_doc_detector.find_missing_documents")
from output.missing_doc_detector import find_missing_documents

clauses = [
    {
        "section_number": "3.1",
        "document_type": "SOW",
        "text": "Deliverables are as specified in Schedule 1 - Project Scope Document.",
    },
    {
        "section_number": "4.2",
        "document_type": "SOW",
        "text": "See Exhibit A for pricing. Payment terms in MSA Section 4.",
    },
    {
        "section_number": "2.0",
        "document_type": "MSA",
        "text": "Terms are standard.",
    },
]

missing = find_missing_documents(clauses, ["msa.pdf", "sow.pdf"])
print(f"  Found {len(missing)} missing document(s):")
for m in missing:
    print(f"    [{m['severity']}] {m['referenced_document']} — in {m['clause_section']}")
assert len(missing) == 2, f"Expected 2, got {len(missing)}"
assert missing[0]["severity"] == "BLOCKER"
print("  PASS ✓")

# ── Test 2: Output Formatter ──────────────────────────────────────────────────
print("\n[2] output_formatter.format_output + summarize")
from output.output_formatter import format_output, summarize

risks = [
    {"type": "CONTRADICTION", "severity": "HIGH",   "original_text": "45 days"},
    {"type": "OVERRIDE",      "severity": "MEDIUM",  "original_text": "uncapped"},
    {"type": "FINANCIAL",     "severity": "LOW",     "original_text": "table"},
]
missing_docs = [
    {"type": "MISSING_DOCUMENT", "severity": "BLOCKER", "referenced_document": "Exhibit A"},
]

combined = format_output(risks, missing_docs)
assert combined[0]["severity"] == "BLOCKER",  "BLOCKER should be first"
assert combined[1]["severity"] == "HIGH",     "HIGH should be second"
assert combined[2]["severity"] == "MEDIUM",   "MEDIUM should be third"
assert combined[3]["severity"] == "LOW",      "LOW should be last"

counts = summarize(combined)
assert counts["total"]   == 4
assert counts["blocker"] == 1
assert counts["high"]    == 1
assert counts["medium"]  == 1
assert counts["low"]     == 1
print(f"  Counts: {counts}")
print("  PASS ✓")

# ── Test 3: Redline Generator (mock mode — no API key needed) ─────────────────
print("\n[3] redline_generator.generate_redlines (mock/fallback mode)")
from output.redline_generator import generate_redlines

sample_risks = [
    {
        "risk_id": "RISK-001",
        "type": "CONTRADICTION",
        "severity": "HIGH",
        "description": "Payment term conflict: SOW 45 days vs MSA 30 days.",
        "original_text": "All milestone payments are due within forty-five (45) days.",
        "suggested_text": "",
        "change_summary": "",
        "confidence": 0.95,
    },
    {
        "risk_id": "RISK-002",
        "type": "OVERRIDE",
        "severity": "MEDIUM",
        "description": "IP override via Notwithstanding clause.",
        "original_text": "Notwithstanding MSA Section 5, code remains Vendor property.",
        "suggested_text": "",
        "change_summary": "",
        "confidence": 0.90,
    },
    {
        "risk_id": "RISK-003",
        "type": "FINANCIAL",
        "severity": "LOW",
        "description": "Financial table detected.",
        "original_text": "See rate table.",
        "suggested_text": "",
        "change_summary": "",
        "confidence": 0.70,
    },
]

enriched = generate_redlines(sample_risks)
assert len(enriched) == 3, f"Expected 3 risks, got {len(enriched)}"

high_risk = next(r for r in enriched if r["severity"] == "HIGH")
assert "redline" in high_risk, "HIGH risk must have redline sub-dict"
assert high_risk["redline"] is not None, "HIGH risk redline must not be None"
assert "suggested_text" in high_risk
assert "change_summary" in high_risk
print(f"  HIGH risk redline: {high_risk['redline']}")

low_risk = next(r for r in enriched if r["severity"] == "LOW")
assert low_risk["redline"] is None, "LOW risk redline must be None"
assert low_risk["change_summary"] == "Review recommended"
print(f"  LOW risk change_summary: '{low_risk['change_summary']}'")
print("  PASS ✓")

# ── Test 4: Full pipeline in mock mode ────────────────────────────────────────
print("\n[4] pipeline.run_analysis (USE_MOCKS=True, canned demo data)")
os.environ["USE_MOCKS"] = "true"

# pipeline is a module-level import, so we need importlib to reload it
import importlib
import pipeline as _pipeline_mod
importlib.reload(_pipeline_mod)

# Create two tiny temp text files
import tempfile
with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
    f.write("Mock MSA content"); msa_path = f.name
with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
    f.write("Mock SOW content"); sow_path = f.name

try:
    result = _pipeline_mod.run_analysis(msa_path, sow_path, "test_msa.txt", "test_sow.txt")
    assert "analysis_id"  in result, "Missing analysis_id"
    assert "summary"      in result, "Missing summary"
    assert "results"      in result, "Missing results"
    assert "graph"        in result, "Missing graph"
    assert "nodes"        in result["graph"], "Graph missing nodes"
    assert "edges"        in result["graph"], "Graph missing edges"
    print(f"  analysis_id: {result['analysis_id']}")
    print(f"  summary: {result['summary']}")
    print(f"  results count: {len(result['results'])}")
    print(f"  graph nodes: {len(result['graph']['nodes'])}, edges: {len(result['graph']['edges'])}")
    print("  PASS ✓")
finally:
    os.unlink(msa_path)
    os.unlink(sow_path)

# ── Test 5: Database save + retrieve ──────────────────────────────────────────
print("\n[5] database.db save_analysis + get_analysis_by_id")
from database.db import save_analysis, get_all_analyses, get_analysis_by_id

record = {
    "msa_filename":   "test_msa.txt",
    "sow_filename":   "test_sow.txt",
    "total_risks":    3,
    "blocker_count":  1,
    "critical_count": 0,
    "high_count":     2,
    "medium_count":   0,
    "low_count":      0,
    "status":         "COMPLETE",
    "results":        [{"type": "CONTRADICTION", "severity": "HIGH"}],
    "clauses":        [{"section_number": "4.1", "document_type": "MSA"}],
    "graph":          {"nodes": [], "edges": []},
}
aid = save_analysis(record)
print(f"  Saved analysis id: {aid}")
assert isinstance(aid, int) and aid > 0

retrieved = get_analysis_by_id(aid)
assert retrieved is not None
assert retrieved["msa_filename"]  == "test_msa.txt"
assert retrieved["total_risks"]   == 3
assert retrieved["blocker_count"] == 1
assert len(retrieved["results"])  == 1
print(f"  Retrieved: msa={retrieved['msa_filename']}, total={retrieved['total_risks']}")

history = get_all_analyses()
assert any(a["id"] == aid for a in history)
print(f"  History has {len(history)} record(s)")
print("  PASS ✓")

print("\n" + "=" * 60)
print("All 5 tests passed.")
print("=" * 60)
print("\nNext: start the server and test the HTTP API:")
print("  cd backend")
print("  uvicorn main:app --reload")
print("  curl http://localhost:8000/health")

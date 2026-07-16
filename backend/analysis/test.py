from risk_pipeline import run_risk_detection
import json

clause_pairs = [{
    "clause_a": {"section_number": "MSA-4.1", "document_type": "MSA", "text": "Payment due within thirty (30) days."},
    "clause_b": {"section_number": "SOW-2.3", "document_type": "SOW", "text": "Payment due within forty-five (45) days."},
}]

all_clauses = [
    {"section_number": "9", "document_type": "SOW", "text": "Notwithstanding MSA Section 7, liability is uncapped."},
    {"section_number": "6", "document_type": "MSA", "text": "Late fee of 1.5% applies, capped at $500."},
]

results = run_risk_detection(clause_pairs, all_clauses)  # no _call_fn = hits the real API
print(json.dumps(results, indent=2))
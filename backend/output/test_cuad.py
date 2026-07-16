"""Run Component 5's real code on real CUAD contract text.

Unlike test_redlines.py (synthetic inputs), this pulls actual clauses out of the
CUAD dataset and runs the missing-doc detector and redline generator on them.

Run from the backend/ directory:
    python -m output.test_cuad

Uses live Gemini if GEMINI_API_KEY is set, else the deterministic mock.
Override the dataset location with CUAD_DIR if yours lives elsewhere.
"""

import glob
import os
import re
import textwrap

from output.missing_doc_detector import find_missing_documents
from output.output_formatter import format_output, summarize
from output.redline_generator import generate_redlines

_DEFAULT_CUAD = (
    "../Data_sets_hackathon-main/challenge-4-contract-sow-risk-analyzer/"
    "data/cuad/CUAD_v1/full_contract_txt"
)
CUAD_DIR = os.environ.get("CUAD_DIR", _DEFAULT_CUAD)

_HEADING = re.compile(r"(?im)^\s*(?:section|article)?\s*(\d+(?:\.\d+)?)[.\s\-—:]")


def _load_contract(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def _to_clauses(text: str, doc_type: str, limit: int = 40) -> list[dict]:
    """Rough clause splitter (stand-in for Components 1+2) for testing C5."""
    clauses, matches = [], list(_HEADING.finditer(text))
    if len(matches) >= 3:
        for i, m in enumerate(matches[:limit]):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = " ".join(text[m.start():end].split())[:600]
            clauses.append({"section_number": m.group(1), "document_type": doc_type, "text": body})
    else:
        for i, chunk in enumerate(re.split(r"\n\s*\n", text)[:limit], start=1):
            clauses.append({"section_number": str(i), "document_type": doc_type,
                            "text": " ".join(chunk.split())[:600]})
    return clauses


def main() -> None:
    files = sorted(glob.glob(os.path.join(CUAD_DIR, "**", "*.txt"), recursive=True))
    if not files:
        print(f"No CUAD .txt files found under: {CUAD_DIR}")
        print("Set CUAD_DIR to your dataset path and retry.")
        return

    contract_path = files[0]
    name = os.path.basename(contract_path)
    print(f"=== Real CUAD contract: {name} ===\n")

    clauses = _to_clauses(_load_contract(contract_path), "MSA")
    print(f"Extracted {len(clauses)} clauses from real text.\n")

    # --- 1. Missing-document detection on real clauses ---------------------
    refusals = find_missing_documents(clauses, uploaded_filenames=[name])
    print(f"[1] Missing-doc detector -> {len(refusals)} BLOCKER refusal(s):")
    for r in refusals[:5]:
        print(f"    • {r['referenced_document']}  (from {r['clause_section']})")
    if not refusals:
        print("    (this contract references no un-provided external documents)")
    print()

    # --- 2. Redlines on a few real clauses --------------------------------
    # Prefer clauses mentioning a term/override; otherwise fall back to the two
    # longest real clauses so there's always genuine contract text to redline.
    interesting = [c for c in clauses
                   if re.search(r"\bnotwithstanding\b|\bdays\b|\bterminate\b", c["text"], re.IGNORECASE)]
    picked = (interesting or sorted(clauses, key=lambda c: len(c["text"]), reverse=True))[:2]
    sample_risks = [{
        "risk_id": f"RISK-{i+1:03d}", "type": "TERM", "severity": "MEDIUM",
        "clause_a_section": f"MSA-{c['section_number']}", "clause_b_section": "",
        "description": "Verify this term aligns with the governing MSA.",
        "original_text": c["text"], "suggested_text": "", "change_summary": "",
    } for i, c in enumerate(picked)]

    print(f"[2] Redline generator on {len(sample_risks)} real clause(s):")
    enriched = generate_redlines(sample_risks)
    for r in enriched:
        print(f"    {r['risk_id']} ({r['clause_a_section']}):")
        print("      before:", textwrap.shorten(r["original_text"], 100))
        print("      after :", textwrap.shorten(r["suggested_text"], 100))
        print("      note  :", r["change_summary"])
    print()

    # --- 3. Combined, sorted output ---------------------------------------
    results = format_output(enriched, refusals)
    print("[3] Combined output summary:", summarize(results))
    print("\nComponent 5 ran successfully on real CUAD data.")


if __name__ == "__main__":
    main()

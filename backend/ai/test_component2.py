"""
Component 2 test — run from the backend/ directory:
    cd backend
    python ai/test_component2.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import glob
from ai.clause_extractor import extract_clauses
from ai.ledgar_loader import LEDGAR_EXAMPLES
from config import CUAD_DIR


# ─── Test 1: LEDGAR examples loaded correctly ────────────────────────────────

def test_ledgar_loaded():
    total = sum(len(v) for v in LEDGAR_EXAMPLES.values())
    assert total > 0, "LEDGAR examples should load at least some examples"
    print(f"[Test 1 PASS] LEDGAR loaded {total} examples across {len(LEDGAR_EXAMPLES)} types")
    for k, v in LEDGAR_EXAMPLES.items():
        print(f"  {k}: {len(v)} example(s)")


# ─── Test 2: Extract clauses from a real CUAD contract ───────────────────────

def test_cuad_extraction():
    # Find any text file in CUAD (full_contract_txt has clean text versions)
    txt_dir = os.path.join(CUAD_DIR, "CUAD_v1", "full_contract_txt")
    txts = glob.glob(os.path.join(txt_dir, "**", "*.txt"), recursive=True)

    if not txts:
        print("[Test 2 SKIP] No CUAD .txt files found — run from project root")
        return

    contract_path = txts[0]
    print(f"\n[Test 2] Testing against: {os.path.basename(contract_path)}")

    with open(contract_path, encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # Simulate what Component 1 returns
    extraction_result = {
        "mode": "text",
        "content": text,
        "file_type": "txt",
        "word_count": len(text.split()),
    }

    clauses = extract_clauses(extraction_result, "MSA", file_path=contract_path)

    print(f"  Clauses extracted: {len(clauses)}")
    assert len(clauses) > 0, "Should extract at least some clauses"

    # Check structure of first clause
    first = clauses[0]
    for field in ("section_number", "title", "text", "document_type", "clause_type", "references_to"):
        assert field in first, f"Missing field: {field}"

    print(f"  First clause: § {first['section_number']} — {first['title']} [{first['clause_type']}]")
    print(f"  Types found: {sorted(set(c['clause_type'] for c in clauses))}")
    print(f"  Clauses with references: {sum(1 for c in clauses if c['references_to'])}")

    tables = [c for c in clauses if c.get("clause_type") == "financial_table"]
    print(f"  Financial tables: {len(tables)}")

    print("[Test 2 PASS]")
    return clauses


# ─── Test 3: Cache works — second call should be instant ─────────────────────

def test_cache(clauses_from_test2=None):
    txts = glob.glob(
        os.path.join(CUAD_DIR, "CUAD_v1", "full_contract_txt", "**", "*.txt"),
        recursive=True,
    )
    if not txts:
        print("[Test 3 SKIP] No CUAD txt files")
        return

    import time
    extraction_result = {
        "mode": "text",
        "content": open(txts[0], encoding="utf-8", errors="ignore").read(),
        "file_type": "txt",
    }

    start = time.time()
    clauses = extract_clauses(extraction_result, "MSA", file_path=txts[0])
    elapsed = time.time() - start

    print(f"\n[Test 3] Second call for same file: {elapsed:.2f}s")
    assert elapsed < 1.0, f"Cache should return in <1s, got {elapsed:.2f}s"
    print("[Test 3 PASS] Cache working correctly")


# ─── Test 4: Compare against CUAD ground truth ───────────────────────────────

def test_cuad_accuracy(clauses):
    if not clauses:
        print("[Test 4 SKIP] No clauses from test 2")
        return

    cuad_json = os.path.join(CUAD_DIR, "CUAD_v1", "CUAD_v1.json")
    if not os.path.exists(cuad_json):
        print("[Test 4 SKIP] CUAD JSON not found")
        return

    with open(cuad_json) as f:
        cuad = json.load(f)

    # Find the contract in CUAD data
    first_contract = cuad["data"][0]
    expert_types = set()
    for para in first_contract.get("paragraphs", []):
        for qa in para.get("qas", []):
            if qa.get("answers"):
                qid = qa.get("id", "")
                if "__" in qid:
                    expert_types.add(qid.split("__")[1].lower().replace(" ", "_"))

    our_types = set(c["clause_type"] for c in clauses)
    overlap   = our_types & expert_types
    print(f"\n[Test 4] CUAD expert types: {len(expert_types)}")
    print(f"  Our types extracted: {our_types}")
    print(f"  Overlap with expert: {len(overlap)} — {overlap}")
    print("[Test 4 DONE]")


if __name__ == "__main__":
    print("=" * 50)
    print("Component 2 — Clause Extractor Tests")
    print("=" * 50)

    test_ledgar_loaded()
    clauses = test_cuad_extraction()
    test_cache()
    test_cuad_accuracy(clauses)

    print("\nAll tests complete.")

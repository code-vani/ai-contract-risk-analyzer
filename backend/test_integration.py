"""Component 10 — Integration test for the full real pipeline.

Run from backend/:
    python test_integration.py
    cd backend && USE_MOCKS=false pytest test_integration.py -v

Requires GEMINI_API_KEY in backend/.env for AI-dependent steps (Components 2 & 4).
Pure-Python steps (Component 3 graph, Component 5 missing-doc detection) always run.

Deliberate issues baked into the sample files:
  1. CONTRADICTION   — MSA §4.1 (30-day payment)  vs  SOW §2.2 (45-day payment)
  2. MISSING_DOCUMENT— SOW §3.1 references "Schedule 1 – Project Scope Document"
  3. CIRCULAR_REF    — SOW §5 → SOW §9 → SOW §5  (cross-references form a cycle)
  4. OVERRIDE        — SOW §6 "Notwithstanding MSA §5" — IP ownership
  5. OVERRIDE        — SOW §7 "Notwithstanding MSA §7" — uncapped liability
  6. CONTRADICTION   — MSA §8.1 (30-day termination) vs SOW §8.1 (7-day termination)
"""

import os
import sys
import importlib

# Must be set BEFORE any project-code imports so config.py picks it up.
os.environ["USE_MOCKS"] = "false"

_BACKEND = os.path.dirname(os.path.abspath(__file__))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Reload config so USE_MOCKS=False takes effect even if a prior test file
# already imported config with USE_MOCKS=True (pytest collects multiple files).
import config as _config_mod
importlib.reload(_config_mod)

import pipeline as _pipeline_mod
importlib.reload(_pipeline_mod)
import pipeline  # reference the now-reloaded module

_HERE = os.path.dirname(os.path.abspath(__file__))
MSA_PATH = os.path.join(_HERE, "demo", "Sample_MSA.docx")
SOW_PATH = os.path.join(_HERE, "demo", "Sample_SOW.docx")
MSA_NAME = "Sample_MSA.docx"
SOW_NAME = "Sample_SOW.docx"

HAS_API_KEY = bool(os.getenv("GEMINI_API_KEY", "").strip())

# Cache one pipeline run per process so tests don't hit the API multiple times.
_RESULT_CACHE: dict = {}


def _run() -> dict:
    if "result" not in _RESULT_CACHE:
        _RESULT_CACHE["result"] = pipeline.run_analysis(
            MSA_PATH, SOW_PATH, MSA_NAME, SOW_NAME
        )
    return _RESULT_CACHE["result"]


# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — Prerequisites (no API call needed)
# ─────────────────────────────────────────────────────────────────────────────

def test_sample_files_exist():
    """Both demo contract files must be present on disk."""
    assert os.path.isfile(MSA_PATH), f"Missing sample file: {MSA_PATH}"
    assert os.path.isfile(SOW_PATH), f"Missing sample file: {SOW_PATH}"


def test_use_mocks_is_false():
    """config.USE_MOCKS must be False so we exercise the real components."""
    assert _config_mod.USE_MOCKS is False, (
        "config.USE_MOCKS is still True — real pipeline not active. "
        "Ensure os.environ['USE_MOCKS']='false' is set before imports."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — Output shape (runs the pipeline; partial results even without key)
# ─────────────────────────────────────────────────────────────────────────────

def test_output_has_required_keys():
    """run_analysis must return all top-level keys the API server expects."""
    result = _run()
    for key in ("analysis_id", "summary", "results", "graph"):
        assert key in result, f"run_analysis output missing required key: '{key}'"


def test_analysis_id_is_positive_int():
    result = _run()
    aid = result["analysis_id"]
    assert isinstance(aid, int) and aid > 0, f"analysis_id should be a positive int, got: {aid!r}"


def test_summary_has_severity_counts():
    result = _run()
    summary = result["summary"]
    for key in ("total", "blocker", "critical", "high", "medium", "low"):
        assert key in summary, f"summary dict missing key: '{key}'"
        assert isinstance(summary[key], int), f"summary['{key}'] should be int"


# ─────────────────────────────────────────────────────────────────────────────
# Group 3 — Component 5: Missing-document detection (pure regex, no API key)
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_document_blocker_detected():
    """SOW §3.1 references 'Schedule 1' which was not uploaded → BLOCKER refusal.

    This is pure regex in missing_doc_detector.py — always runs regardless of key.
    """
    result = _run()
    missing = result.get("missing_docs", [])
    schedule_refs = [
        m for m in missing
        if "Schedule" in m.get("referenced_document", "")
    ]
    assert len(schedule_refs) >= 1, (
        f"Expected at least one BLOCKER for 'Schedule 1' (SOW §3.1), got: {missing}"
    )
    assert all(m.get("severity") == "BLOCKER" for m in schedule_refs), (
        f"Missing-document findings should be BLOCKER severity: {schedule_refs}"
    )


def test_blocker_count_reflects_missing_doc():
    """summary.blocker must be >= 1 because of the Schedule 1 missing-doc finding."""
    result = _run()
    assert result["summary"]["blocker"] >= 1, (
        "Expected blocker count >= 1 (Schedule 1 missing doc), "
        f"got summary: {result['summary']}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 4 — Component 3: Dependency graph (pure Python, no API key)
# ─────────────────────────────────────────────────────────────────────────────

def test_graph_has_nodes():
    """Component 3 must produce at least one clause node from the sample files."""
    result = _run()
    nodes = result["graph"].get("nodes", [])
    assert len(nodes) > 0, "Graph has zero nodes — Component 3 produced no output."


def test_graph_contains_both_document_types():
    """Graph must have nodes from both MSA and SOW."""
    result = _run()
    doc_types = {n.get("document_type", "") for n in result["graph"].get("nodes", [])}
    assert "MSA" in doc_types, f"No MSA nodes in graph. Found types: {doc_types}"
    assert "SOW" in doc_types, f"No SOW nodes in graph. Found types: {doc_types}"


def test_graph_nodes_have_required_fields():
    """Every graph node must have id, label, and document_type."""
    result = _run()
    for node in result["graph"].get("nodes", []):
        for field in ("id", "label", "document_type"):
            assert field in node, (
                f"Graph node missing required field '{field}': {node}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Group 5 — Component 9: Database round-trip (real SQLite, no API key)
# ─────────────────────────────────────────────────────────────────────────────

def test_db_save_and_retrieve_roundtrip():
    """save_analysis + get_analysis_by_id must round-trip through real SQLite."""
    from adapters.real_pipeline import save_analysis, get_analysis_by_id, get_all_analyses

    record = {
        "msa_filename": "Integration_Test_MSA.txt",
        "sow_filename": "Integration_Test_SOW.txt",
        "total_risks":   4,
        "blocker_count": 1,
        "critical_count": 1,
        "high_count":    2,
        "medium_count":  0,
        "low_count":     0,
        "status": "COMPLETE",
        "results": [
            {"type": "MISSING_DOCUMENT", "severity": "BLOCKER",
             "referenced_document": "Schedule 1"},
            {"type": "CONTRADICTION", "severity": "CRITICAL",
             "description": "Payment terms conflict: MSA 30d vs SOW 45d"},
        ],
        "clauses": [
            {"section_number": "4.1", "document_type": "MSA",
             "text": "Payment within thirty (30) days."},
        ],
        "graph": {"nodes": [], "edges": [], "circular_references": []},
    }

    aid = save_analysis(record)
    assert isinstance(aid, int) and aid > 0, f"save_analysis returned: {aid!r}"

    retrieved = get_analysis_by_id(aid)
    assert retrieved is not None, f"get_analysis_by_id({aid}) returned None"
    assert retrieved.get("msa_filename") == "Integration_Test_MSA.txt"
    assert retrieved.get("blocker_count") == 1
    assert retrieved.get("critical_count") == 1

    history = get_all_analyses()
    saved_ids = [row["id"] for row in history]
    assert aid in saved_ids, (
        f"Saved id {aid} not found in get_all_analyses() result: {saved_ids}"
    )


def test_run_analysis_result_persisted_in_db():
    """The analysis_id returned by run_analysis must be retrievable from the DB."""
    from adapters.real_pipeline import get_analysis_by_id

    result = _run()
    aid = result["analysis_id"]
    stored = get_analysis_by_id(aid)
    assert stored is not None, (
        f"run_analysis returned analysis_id={aid} but get_analysis_by_id returned None"
    )
    assert stored.get("msa_filename") == MSA_NAME
    assert stored.get("sow_filename") == SOW_NAME


# ─────────────────────────────────────────────────────────────────────────────
# Group 6 — AI-dependent assertions (skipped if no GEMINI_API_KEY)
# ─────────────────────────────────────────────────────────────────────────────

def _skip_if_no_key(test_name: str) -> bool:
    if not HAS_API_KEY:
        print(f"  SKIP  {test_name}: GEMINI_API_KEY not set")
        return True
    return False


def test_risk_list_nonempty_with_key():
    """At least one risk must be detected when the API key is present."""
    if _skip_if_no_key("test_risk_list_nonempty_with_key"):
        return
    result = _run()
    assert len(result.get("results", [])) > 0, (
        "Expected at least one risk with real Gemini key. "
        "Components 2 & 4 may not be detecting the deliberate contradictions."
    )


def test_payment_contradiction_detected():
    """MSA §4.1 (30 days) vs SOW §2.2 (45 days) must produce a CONTRADICTION.

    Skipped without API key — requires Component 4's Gemini-powered detection.
    """
    if _skip_if_no_key("test_payment_contradiction_detected"):
        return
    result = _run()
    findings = result.get("results", [])
    hits = [
        r for r in findings
        if r.get("type") == "CONTRADICTION"
        and any(kw in (r.get("description", "") + r.get("original_text", "")).lower()
                for kw in ("payment", "invoice", "30", "45"))
    ]
    assert len(hits) >= 1, (
        "Expected CONTRADICTION for payment terms (MSA:30d vs SOW:45d). "
        f"All findings: {[(r.get('type'), r.get('description', '')[:60]) for r in findings]}"
    )


def test_ip_override_detected():
    """SOW §6 'Notwithstanding MSA §5' must produce an OVERRIDE finding.

    Skipped without API key — requires Component 4's Gemini-powered detection.
    """
    if _skip_if_no_key("test_ip_override_detected"):
        return
    result = _run()
    findings = result.get("results", [])
    hits = [
        r for r in findings
        if r.get("type") in ("OVERRIDE", "CONTRADICTION")
        and any(kw in (r.get("description", "") + r.get("original_text", "")).lower()
                for kw in ("ip", "intellectual property", "ownership", "notwithstanding"))
    ]
    assert len(hits) >= 1, (
        "Expected OVERRIDE for IP ownership (SOW §6 Notwithstanding MSA §5). "
        f"All findings: {[(r.get('type'), r.get('description', '')[:60]) for r in findings]}"
    )


def test_liability_override_detected():
    """SOW §7.1 'Notwithstanding MSA §7' (uncapped liability) must be flagged.

    Skipped without API key.
    """
    if _skip_if_no_key("test_liability_override_detected"):
        return
    result = _run()
    findings = result.get("results", [])
    hits = [
        r for r in findings
        if r.get("type") in ("OVERRIDE", "CONTRADICTION")
        and any(kw in (r.get("description", "") + r.get("original_text", "")).lower()
                for kw in ("liab", "uncapped", "unlimited", "data breach", "cybersecurity"))
    ]
    assert len(hits) >= 1, (
        "Expected OVERRIDE for uncapped liability (SOW §7 Notwithstanding MSA §7). "
        f"All findings: {[(r.get('type'), r.get('description', '')[:60]) for r in findings]}"
    )


def test_termination_contradiction_detected():
    """MSA §8.1 (30-day notice) vs SOW §8.1 (7-day notice) must be flagged.

    Skipped without API key.
    """
    if _skip_if_no_key("test_termination_contradiction_detected"):
        return
    result = _run()
    findings = result.get("results", [])
    hits = [
        r for r in findings
        if r.get("type") == "CONTRADICTION"
        and any(kw in (r.get("description", "") + r.get("original_text", "")).lower()
                for kw in ("terminat", "notice", "7", "seven", "30", "thirty"))
    ]
    assert len(hits) >= 1, (
        "Expected CONTRADICTION for termination notice (MSA:30d vs SOW:7d). "
        f"All findings: {[(r.get('type'), r.get('description', '')[:60]) for r in findings]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Direct runner  →  python test_integration.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = [
        # Group 1 — prerequisites
        test_sample_files_exist,
        test_use_mocks_is_false,
        # Group 2 — output shape
        test_output_has_required_keys,
        test_analysis_id_is_positive_int,
        test_summary_has_severity_counts,
        # Group 3 — missing-doc detection (pure regex)
        test_missing_document_blocker_detected,
        test_blocker_count_reflects_missing_doc,
        # Group 4 — graph (pure Python)
        test_graph_has_nodes,
        test_graph_contains_both_document_types,
        test_graph_nodes_have_required_fields,
        # Group 5 — database round-trip
        test_db_save_and_retrieve_roundtrip,
        test_run_analysis_result_persisted_in_db,
        # Group 6 — AI-dependent (skipped without key)
        test_risk_list_nonempty_with_key,
        test_payment_contradiction_detected,
        test_ip_override_detected,
        test_liability_override_detected,
        test_termination_contradiction_detected,
    ]

    passed = skipped = failed = 0
    print(f"\nRunning Component 10 integration tests")
    print(f"API key present: {HAS_API_KEY}")
    print("-" * 60)

    for t in tests:
        try:
            t()
            # _skip_if_no_key prints "SKIP" and returns — no exception, counts as passed
            name = t.__name__
            if not HAS_API_KEY and name.startswith("test_") and name not in (
                "test_sample_files_exist", "test_use_mocks_is_false",
                "test_output_has_required_keys", "test_analysis_id_is_positive_int",
                "test_summary_has_severity_counts", "test_missing_document_blocker_detected",
                "test_blocker_count_reflects_missing_doc", "test_graph_has_nodes",
                "test_graph_contains_both_document_types", "test_graph_nodes_have_required_fields",
                "test_db_save_and_retrieve_roundtrip", "test_run_analysis_result_persisted_in_db",
            ):
                skipped += 1
            else:
                print(f"  PASS  {t.__name__}")
                passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print("-" * 60)
    print(f"{passed} passed  |  {skipped} skipped (no API key)  |  {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)

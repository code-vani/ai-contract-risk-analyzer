"""
test_detector.py

Full test suite for Component 4. Runs entirely offline — contradiction
detector tests use an injected fake `_call_fn` instead of hitting the real
Gemini API, so this works with zero API key and zero network access.

Run with:  python -m pytest backend/analysis/test_detector.py -v
       or:  python backend/analysis/test_detector.py
"""

import json
import os
import sys
import unittest

# Make imports work regardless of where pytest / python is invoked from:
# workspace root, backend/, or backend/analysis/ all work.
_ANALYSIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_ANALYSIS_DIR)
_WORKSPACE_ROOT = os.path.dirname(_BACKEND_ROOT)
for _p in (_ANALYSIS_DIR, _BACKEND_ROOT, _WORKSPACE_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from contradiction_detector import detect_contradiction, detect_all_contradictions
from override_detector import detect_overrides
from financial_risk_detector import detect_financial_risks
from risk_ranker import rank_risks
from risk_pipeline import run_risk_detection, normalize_risks
from contractnli_evaluator import evaluate_against_contractnli, _extract_contradiction_pairs



# ---------------------------------------------------------------------------
# Fake Gemini callers for testing contradiction_detector without a real API
# ---------------------------------------------------------------------------

def fake_gemini_contradiction(prompt: str) -> str:
    return json.dumps({
        "is_contradiction": True,
        "severity": "HIGH",
        "description": "SOW allows 45 days; MSA requires 30 days.",
        "which_wins": "MSA governs unless overridden.",
        "confidence": 0.95,
    })


def fake_gemini_no_contradiction(prompt: str) -> str:
    return json.dumps({
        "is_contradiction": False,
        "severity": "LOW",
        "description": "Both clauses describe confidentiality obligations consistently.",
        "which_wins": "N/A",
        "confidence": 0.9,
    })


def fake_gemini_unavailable(prompt: str):
    return None  # simulates missing API key / network failure


def fake_gemini_markdown_wrapped(prompt: str) -> str:
    # Simulates Gemini ignoring the "no markdown" instruction
    return "```json\n" + json.dumps({
        "is_contradiction": True,
        "severity": "MEDIUM",
        "description": "Termination notice periods differ.",
        "which_wins": "SOW's 7-day notice likely controls for this engagement.",
        "confidence": 0.7,
    }) + "\n```"


def fake_gemini_garbage_then_fixed():
    """Returns garbage on first call, valid JSON on retry (stateful fake)."""
    calls = {"count": 0}

    def _fn(prompt: str):
        calls["count"] += 1
        if calls["count"] == 1:
            return "Sure! Here's the analysis: {is_contradiction: true, severity: HIGH"  # broken JSON
        return json.dumps({
            "is_contradiction": True,
            "severity": "HIGH",
            "description": "Fixed on retry.",
            "which_wins": "MSA governs.",
            "confidence": 0.8,
        })
    return _fn


def fake_gemini_always_garbage(prompt: str) -> str:
    return "This is not JSON at all, sorry."


# ---------------------------------------------------------------------------
# Contradiction detector tests
# ---------------------------------------------------------------------------

class TestContradictionDetector(unittest.TestCase):

    def setUp(self):
        self.clause_a = {"section_number": "MSA-4.1", "text": "Payment due within thirty (30) days."}
        self.clause_b = {"section_number": "SOW-2.3", "text": "Payment due within forty-five (45) days."}

    def test_detects_real_contradiction(self):
        result = detect_contradiction(self.clause_a, self.clause_b, _call_fn=fake_gemini_contradiction)
        self.assertTrue(result["is_contradiction"])
        self.assertEqual(result["severity"], "HIGH")
        self.assertGreater(result["confidence"], 0.9)

    def test_no_false_positive_on_consistent_clauses(self):
        result = detect_contradiction(self.clause_a, self.clause_b, _call_fn=fake_gemini_no_contradiction)
        self.assertFalse(result["is_contradiction"])

    def test_empty_clause_a_text(self):
        empty = {"section_number": "MSA-1", "text": ""}
        result = detect_contradiction(empty, self.clause_b, _call_fn=fake_gemini_contradiction)
        self.assertFalse(result["is_contradiction"])
        self.assertIn("no extractable text", result["description"])

    def test_empty_clause_b_text(self):
        empty = {"section_number": "SOW-1", "text": None}  # None, not just "" — extra edge case
        result = detect_contradiction(self.clause_a, empty, _call_fn=fake_gemini_contradiction)
        self.assertFalse(result["is_contradiction"])

    def test_identical_clause_self_comparison(self):
        result = detect_contradiction(self.clause_a, self.clause_a, _call_fn=fake_gemini_contradiction)
        self.assertFalse(result["is_contradiction"])
        self.assertIn("identical", result["description"])

    def test_api_unavailable_does_not_crash(self):
        result = detect_contradiction(self.clause_a, self.clause_b, _call_fn=fake_gemini_unavailable)
        self.assertFalse(result["is_contradiction"])
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("unavailable", result["description"])

    def test_strips_markdown_fences(self):
        result = detect_contradiction(self.clause_a, self.clause_b, _call_fn=fake_gemini_markdown_wrapped)
        self.assertTrue(result["is_contradiction"])
        self.assertEqual(result["severity"], "MEDIUM")

    def test_retries_once_on_malformed_json(self):
        result = detect_contradiction(self.clause_a, self.clause_b, _call_fn=fake_gemini_garbage_then_fixed())
        self.assertTrue(result["is_contradiction"])
        self.assertEqual(result["description"], "Fixed on retry.")

    def test_gives_up_gracefully_after_failed_retry(self):
        result = detect_contradiction(self.clause_a, self.clause_b, _call_fn=fake_gemini_always_garbage)
        self.assertFalse(result["is_contradiction"])
        self.assertIn("could not be parsed", result["description"])

    def test_invalid_severity_defaults_to_low(self):
        def fn(prompt):
            return json.dumps({"is_contradiction": True, "severity": "CATASTROPHIC", "confidence": 0.5})
        result = detect_contradiction(self.clause_a, self.clause_b, _call_fn=fn)
        self.assertEqual(result["severity"], "LOW")

    def test_confidence_clamped_to_valid_range(self):
        def fn(prompt):
            return json.dumps({"is_contradiction": True, "severity": "HIGH", "confidence": 5.7})
        result = detect_contradiction(self.clause_a, self.clause_b, _call_fn=fn)
        self.assertEqual(result["confidence"], 1.0)

    def test_missing_fields_filled_with_defaults(self):
        def fn(prompt):
            return json.dumps({"is_contradiction": True})  # only one field present
        result = detect_contradiction(self.clause_a, self.clause_b, _call_fn=fn)
        self.assertIn("description", result)
        self.assertIn("which_wins", result)
        self.assertEqual(result["severity"], "LOW")

    def test_very_long_clause_text_does_not_crash(self):
        long_clause = {"section_number": "MSA-99", "text": "x" * 50000}
        result = detect_contradiction(long_clause, self.clause_b, _call_fn=fake_gemini_contradiction)
        self.assertIn("is_contradiction", result)


class TestBatchContradictionDetection(unittest.TestCase):

    def test_empty_pairs_list(self):
        self.assertEqual(detect_all_contradictions([]), [])

    def test_processes_multiple_pairs(self):
        pairs = [
            {"clause_a": {"section_number": "MSA-1", "text": "30 days"}, "clause_b": {"section_number": "SOW-1", "text": "45 days"}},
            {"clause_a": {"section_number": "MSA-2", "text": "IP owned by client"}, "clause_b": {"section_number": "SOW-2", "text": "IP owned by client"}},
        ]
        results = detect_all_contradictions(pairs, delay_seconds=0, _call_fn=fake_gemini_contradiction)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["type"] == "CONTRADICTION" for r in results))

    def test_skips_malformed_pair_without_crashing_batch(self):
        pairs = [
            {"clause_a": None, "clause_b": {"section_number": "SOW-1", "text": "text"}},  # malformed
            {"clause_a": {"section_number": "MSA-2", "text": "30 days"}, "clause_b": {"section_number": "SOW-2", "text": "45 days"}},
        ]
        results = detect_all_contradictions(pairs, delay_seconds=0, _call_fn=fake_gemini_contradiction)
        self.assertEqual(len(results), 1)  # only the valid pair produced a result

    def test_only_returns_actual_contradictions(self):
        pairs = [
            {"clause_a": {"section_number": "MSA-1", "text": "A"}, "clause_b": {"section_number": "SOW-1", "text": "B"}},
        ]
        results = detect_all_contradictions(pairs, delay_seconds=0, _call_fn=fake_gemini_no_contradiction)
        self.assertEqual(results, [])  # non-contradictions are filtered out, not returned as risks


# ---------------------------------------------------------------------------
# Override detector tests
# ---------------------------------------------------------------------------

class TestOverrideDetector(unittest.TestCase):

    def test_detects_override_with_named_section(self):
        clauses = [{"section_number": "7", "document_type": "SOW",
                    "text": "Notwithstanding MSA Section 8, liability is uncapped."}]
        results = detect_overrides(clauses)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["overridden_section"], "8")
        self.assertEqual(results[0]["severity"], "HIGH")

    def test_detects_override_without_named_section(self):
        clauses = [{"section_number": "9", "document_type": "SOW",
                    "text": "Notwithstanding anything to the contrary herein, this applies."}]
        results = detect_overrides(clauses)
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0]["overridden_section"])

    def test_multiple_overrides_in_one_clause(self):
        clauses = [{"section_number": "5", "document_type": "SOW",
                    "text": "Notwithstanding Section 3, X applies. Also, notwithstanding Section 9, Y applies."}]
        results = detect_overrides(clauses)
        self.assertEqual(len(results), 2)

    def test_no_override_language_returns_empty(self):
        clauses = [{"section_number": "2", "document_type": "MSA", "text": "This is a plain clause."}]
        self.assertEqual(detect_overrides(clauses), [])

    def test_empty_text_skipped(self):
        clauses = [{"section_number": "1", "document_type": "SOW", "text": ""}]
        self.assertEqual(detect_overrides(clauses), [])

    def test_empty_clause_list(self):
        self.assertEqual(detect_overrides([]), [])

    def test_case_insensitive_match(self):
        clauses = [{"section_number": "4", "document_type": "SOW", "text": "notwithstanding section 2, terms differ."}]
        results = detect_overrides(clauses)
        self.assertEqual(len(results), 1)

    def test_malformed_clause_missing_keys(self):
        # Only 'text' present, no section_number/document_type — must not crash
        clauses = [{"text": "Notwithstanding Section 1, this applies."}]
        results = detect_overrides(clauses)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["overriding_clause_section"], "UNKNOWN")


# ---------------------------------------------------------------------------
# Financial risk detector tests
# ---------------------------------------------------------------------------

class TestFinancialRiskDetector(unittest.TestCase):

    def test_flags_dollar_amount(self):
        clauses = [{"section_number": "6", "document_type": "SOW", "text": "Total contract value is $250,000."}]
        results = detect_financial_risks(clauses)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "FINANCIAL_CLAUSE")

    def test_flags_percentage(self):
        clauses = [{"section_number": "4.1", "document_type": "MSA", "text": "Late fee of 1.5% applies monthly."}]
        results = detect_financial_risks(clauses)
        self.assertEqual(len(results), 1)

    def test_flags_financial_keyword_with_number(self):
        clauses = [{"section_number": "8", "document_type": "SOW", "text": "A penalty of 2 units per day of delay applies."}]
        results = detect_financial_risks(clauses)
        self.assertEqual(len(results), 1)

    def test_does_not_flag_plain_number_clause(self):
        # "30 days" alone should NOT trigger a financial flag — this is the
        # false-positive case the naive "any digit" approach would get wrong.
        clauses = [{"section_number": "2", "document_type": "MSA", "text": "Delivery occurs within 30 days of signing."}]
        results = detect_financial_risks(clauses)
        self.assertEqual(results, [])

    def test_empty_text_skipped(self):
        clauses = [{"section_number": "1", "document_type": "SOW", "text": ""}]
        self.assertEqual(detect_financial_risks(clauses), [])

    def test_empty_clause_list(self):
        self.assertEqual(detect_financial_risks([]), [])

    def test_keyword_without_number_not_flagged(self):
        # "cap" appears but with no accompanying number — should not falsely trigger
        clauses = [{"section_number": "3", "document_type": "MSA", "text": "Liability shall be capped as described elsewhere."}]
        results = detect_financial_risks(clauses)
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# Risk ranker tests
# ---------------------------------------------------------------------------

class TestRiskRanker(unittest.TestCase):

    def test_sorts_by_severity(self):
        risks = [
            {"severity": "LOW", "type": "A"},
            {"severity": "HIGH", "type": "B"},
            {"severity": "MEDIUM", "type": "C"},
        ]
        ranked = rank_risks(risks)
        self.assertEqual([r["severity"] for r in ranked], ["HIGH", "MEDIUM", "LOW"])

    def test_blocker_sorts_first(self):
        risks = [{"severity": "HIGH"}, {"severity": "BLOCKER"}]
        ranked = rank_risks(risks)
        self.assertEqual(ranked[0]["severity"], "BLOCKER")

    def test_assigns_sequential_ids(self):
        risks = [{"severity": "HIGH"}, {"severity": "LOW"}, {"severity": "MEDIUM"}]
        ranked = rank_risks(risks)
        self.assertEqual([r["risk_id"] for r in ranked], ["RISK-001", "RISK-002", "RISK-003"])

    def test_stable_sort_preserves_order_within_severity(self):
        risks = [
            {"severity": "HIGH", "type": "first"},
            {"severity": "HIGH", "type": "second"},
        ]
        ranked = rank_risks(risks)
        self.assertEqual(ranked[0]["type"], "first")
        self.assertEqual(ranked[1]["type"], "second")

    def test_unknown_severity_sorts_last_and_is_labeled(self):
        risks = [{"severity": "LOW"}, {"severity": "URGENT"}]
        ranked = rank_risks(risks)
        self.assertEqual(ranked[-1]["severity"], "URGENT")

    def test_empty_list(self):
        self.assertEqual(rank_risks([]), [])

    def test_does_not_mutate_input(self):
        risks = [{"severity": "HIGH"}]
        rank_risks(risks)
        self.assertNotIn("risk_id", risks[0])  # original dict untouched


# ---------------------------------------------------------------------------
# normalize_risks / run_risk_detection tests (risk_pipeline.py)
# ---------------------------------------------------------------------------

class TestNormalizeRisks(unittest.TestCase):

    def test_adds_confidence_to_override_and_financial_risks(self):
        risks = [
            {"type": "OVERRIDE", "severity": "HIGH", "description": "d"},
            {"type": "FINANCIAL_CLAUSE", "severity": "MEDIUM", "description": "d"},
        ]
        normalized = normalize_risks(risks)
        self.assertTrue(all(r["confidence"] == 1.0 for r in normalized))

    def test_preserves_existing_confidence(self):
        risks = [{"type": "CONTRADICTION", "severity": "HIGH", "confidence": 0.42,
                   "clause_a": {"text": "a"}, "clause_b": {"text": "b"}}]
        normalized = normalize_risks(risks)
        self.assertEqual(normalized[0]["confidence"], 0.42)

    def test_pulls_original_text_from_clause_b_for_contradictions(self):
        risks = [{"type": "CONTRADICTION", "severity": "HIGH",
                   "clause_a": {"text": "30 days"}, "clause_b": {"text": "45 days"}}]
        normalized = normalize_risks(risks)
        self.assertEqual(normalized[0]["original_text"], "45 days")

    def test_pulls_original_text_from_matched_text_for_overrides(self):
        risks = [{"type": "OVERRIDE", "severity": "HIGH",
                   "matched_text": "Notwithstanding Section 8...", "description": "fallback"}]
        normalized = normalize_risks(risks)
        self.assertEqual(normalized[0]["original_text"], "Notwithstanding Section 8...")

    def test_does_not_mutate_input(self):
        risks = [{"type": "OVERRIDE", "severity": "HIGH", "description": "d"}]
        normalize_risks(risks)
        self.assertNotIn("confidence", risks[0])

    def test_empty_list(self):
        self.assertEqual(normalize_risks([]), [])

    def test_idempotent(self):
        risks = [{"type": "OVERRIDE", "severity": "HIGH", "description": "d"}]
        once = normalize_risks(risks)
        twice = normalize_risks(once)
        self.assertEqual(once, twice)


class TestRunRiskDetection(unittest.TestCase):

    def test_combines_all_three_detector_types(self):
        pairs = [{
            "clause_a": {"section_number": "MSA-1", "text": "30 days"},
            "clause_b": {"section_number": "SOW-1", "text": "45 days"},
        }]
        clauses = [
            {"section_number": "9", "document_type": "SOW",
             "text": "Notwithstanding MSA Section 7, liability is uncapped."},
            {"section_number": "6", "document_type": "MSA",
             "text": "Late fee of 1.5% applies, capped at $500."},
        ]
        results = run_risk_detection(pairs, clauses, delay_seconds=0, _call_fn=fake_gemini_contradiction)
        types_found = {r["type"] for r in results}
        self.assertEqual(types_found, {"CONTRADICTION", "OVERRIDE", "FINANCIAL_CLAUSE"})

    def test_every_result_has_risk_id_confidence_and_original_text(self):
        pairs = [{
            "clause_a": {"section_number": "MSA-1", "text": "30 days"},
            "clause_b": {"section_number": "SOW-1", "text": "45 days"},
        }]
        clauses = [{"section_number": "9", "document_type": "SOW",
                     "text": "Notwithstanding Section 7, X applies."}]
        results = run_risk_detection(pairs, clauses, delay_seconds=0, _call_fn=fake_gemini_contradiction)
        for r in results:
            self.assertIn("risk_id", r)
            self.assertIn("confidence", r)
            self.assertIn("original_text", r)

    def test_sorted_high_to_low(self):
        pairs = [{
            "clause_a": {"section_number": "MSA-1", "text": "30 days"},
            "clause_b": {"section_number": "SOW-1", "text": "45 days"},
        }]
        clauses = [{"section_number": "6", "document_type": "MSA",
                     "text": "A fee of $10 applies."}]  # -> MEDIUM
        results = run_risk_detection(pairs, clauses, delay_seconds=0, _call_fn=fake_gemini_contradiction)
        order = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        severities = [order.get(r["severity"], 99) for r in results]
        self.assertEqual(severities, sorted(severities))

    def test_one_detector_failing_does_not_kill_the_others(self):
        # override_detector.detect_overrides will raise on a non-list input
        # if all_clauses is malformed; run_risk_detection must still return
        # whatever the other detectors found instead of raising.
        pairs = [{
            "clause_a": {"section_number": "MSA-1", "text": "30 days"},
            "clause_b": {"section_number": "SOW-1", "text": "45 days"},
        }]
        results = run_risk_detection(pairs, "not-a-list", delay_seconds=0, _call_fn=fake_gemini_contradiction)
        self.assertTrue(any(r["type"] == "CONTRADICTION" for r in results))

    def test_empty_everything_returns_empty_list(self):
        self.assertEqual(run_risk_detection([], [], delay_seconds=0, _call_fn=fake_gemini_contradiction), [])


# ---------------------------------------------------------------------------
# ContractNLI evaluator tests (contractnli_evaluator.py)
# ---------------------------------------------------------------------------

class TestContractNLIEvaluator(unittest.TestCase):

    def _write_fixture(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_missing_dataset_file_returns_zero_result_not_crash(self):
        result = evaluate_against_contractnli(dataset_path="/tmp/does-not-exist-contract-nli.json")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["correct"], 0)
        self.assertIn("error", result)

    def test_unparseable_dataset_file_returns_zero_result_not_crash(self):
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                f.write("this is not valid json {{{")
            result = evaluate_against_contractnli(dataset_path=path)
            self.assertEqual(result["total"], 0)
            self.assertIn("error", result)
        finally:
            os.remove(path)

    def test_extracts_pairs_with_inline_hypothesis(self):
        # Shape where "hypothesis" lives directly on the annotation.
        raw = {
            "documents": {
                "doc1": {
                    "text": "This NDA governs confidential information shared between parties.",
                    "annotation_sets": [{
                        "annotations": {
                            "nda-1": {"choice": "Contradiction", "hypothesis": "The NDA has no term limit."},
                            "nda-2": {"choice": "Entailment", "hypothesis": "Confidentiality is required."},
                        }
                    }],
                }
            }
        }
        pairs = _extract_contradiction_pairs(raw, limit=10)
        self.assertEqual(len(pairs), 1)  # only the Contradiction-labelled one
        self.assertEqual(pairs[0]["clause_b"]["text"], "The NDA has no term limit.")

    def test_extracts_pairs_with_hypothesis_in_separate_labels_map(self):
        # Shape where "hypothesis" lives in a top-level `labels` map keyed
        # by the same id as the annotation, not inline on the annotation.
        raw = {
            "documents": [
                {
                    "text": "This NDA governs confidential information shared between parties.",
                    "labels": {"nda-1": {"hypothesis": "The receiving party may disclose freely."}},
                    "annotation_sets": [{
                        "annotations": {"nda-1": {"choice": "Contradiction"}},
                    }],
                }
            ]
        }
        pairs = _extract_contradiction_pairs(raw, limit=10)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["clause_b"]["text"], "The receiving party may disclose freely.")

    def test_extracts_pairs_from_flat_kiddothe2b_mirror_format(self):
        # Shape used by the working kiddothe2b/contract-nli HF mirror —
        # a flat list of {premise, hypothesis, label} rows (0=contradiction).
        raw = [
            {"premise": "Recipient shall keep information confidential.",
             "hypothesis": "Confidential Information shall only include technical information.",
             "label": 0},
            {"premise": "Recipient may disclose to affiliates.",
             "hypothesis": "Some obligations survive termination.",
             "label": 1},  # entailment — must be excluded
            {"premise": "Recipient may disclose to affiliates.",
             "hypothesis": "Party may retain copies.",
             "label": 2},  # neutral — must be excluded
        ]
        pairs = _extract_contradiction_pairs(raw, limit=10)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["clause_a"]["text"], "Recipient shall keep information confidential.")
        self.assertEqual(
            pairs[0]["clause_b"]["text"],
            "Confidential Information shall only include technical information.",
        )

    def test_flat_format_accepts_string_label_too(self):
        raw = [{"premise": "p", "hypothesis": "h", "label": "0contradiction"}]
        pairs = _extract_contradiction_pairs(raw, limit=10)
        self.assertEqual(len(pairs), 1)

    def test_flat_format_respects_limit(self):
        raw = [{"premise": f"p{i}", "hypothesis": f"h{i}", "label": 0} for i in range(5)]
        pairs = _extract_contradiction_pairs(raw, limit=2)
        self.assertEqual(len(pairs), 2)

    def test_flat_format_skips_malformed_rows(self):
        raw = [None, "not-a-dict", {"premise": "p"}, {"hypothesis": "h"}, {}]
        pairs = _extract_contradiction_pairs(raw, limit=10)
        self.assertEqual(pairs, [])  # nothing usable, no exception raised

    def test_non_contradiction_labels_are_excluded(self):
        raw = {
            "documents": {
                "doc1": {
                    "text": "Sample NDA text.",
                    "annotation_sets": [{
                        "annotations": {
                            "a": {"choice": "Entailment", "hypothesis": "x"},
                            "b": {"choice": "NotMentioned", "hypothesis": "y"},
                        }
                    }],
                }
            }
        }
        pairs = _extract_contradiction_pairs(raw, limit=10)
        self.assertEqual(pairs, [])

    def test_respects_limit(self):
        raw = {
            "documents": {
                "doc1": {
                    "text": "Sample NDA text.",
                    "annotation_sets": [{
                        "annotations": {
                            f"a{i}": {"choice": "Contradiction", "hypothesis": f"hyp {i}"}
                            for i in range(5)
                        }
                    }],
                }
            }
        }
        pairs = _extract_contradiction_pairs(raw, limit=2)
        self.assertEqual(len(pairs), 2)

    def test_malformed_document_entries_are_skipped_not_fatal(self):
        raw = {"documents": [None, "not-a-dict", {"text": ""}, {}]}
        pairs = _extract_contradiction_pairs(raw, limit=10)
        self.assertEqual(pairs, [])  # nothing usable, but no exception raised

    def test_end_to_end_scoring_with_fake_call_fn(self):
        raw = {
            "documents": {
                "doc1": {
                    "text": "Sample NDA text about confidentiality.",
                    "annotation_sets": [{
                        "annotations": {
                            "a1": {"choice": "Contradiction", "hypothesis": "hyp one"},
                            "a2": {"choice": "Contradiction", "hypothesis": "hyp two"},
                        }
                    }],
                }
            }
        }
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(raw, f)

            result = evaluate_against_contractnli(
                n_samples=10, dataset_path=path, delay_seconds=0, _call_fn=fake_gemini_contradiction
            )
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["correct"], 2)
            self.assertEqual(result["accuracy_pct"], 100)
            self.assertNotIn("error", result)
        finally:
            os.remove(path)

    def test_partial_accuracy_reports_missed_examples(self):
        raw = {
            "documents": {
                "doc1": {
                    "text": "Sample NDA text.",
                    "annotation_sets": [{
                        "annotations": {
                            "a1": {"choice": "Contradiction", "hypothesis": "hyp one"},
                            "a2": {"choice": "Contradiction", "hypothesis": "hyp two"},
                        }
                    }],
                }
            }
        }
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(raw, f)

            result = evaluate_against_contractnli(
                n_samples=10, dataset_path=path, delay_seconds=0, _call_fn=fake_gemini_no_contradiction
            )
            self.assertEqual(result["correct"], 0)
            self.assertEqual(result["accuracy_pct"], 0)
            self.assertEqual(len(result["missed_examples"]), 2)
        finally:
            os.remove(path)


# ---------------------------------------------------------------------------
# Enhanced override detector — new patterns and which_wins field
# ---------------------------------------------------------------------------

class TestOverrideDetectorEnhanced(unittest.TestCase):

    def test_detects_supersedes_with_section(self):
        clauses = [{"section_number": "3", "document_type": "SOW",
                    "text": "This SOW supersedes Section 4 of the MSA for this engagement."}]
        results = detect_overrides(clauses)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["overridden_section"], "4")

    def test_detects_in_lieu_of_with_section(self):
        clauses = [{"section_number": "5", "document_type": "SOW",
                    "text": "In lieu of Section 8 of the MSA, the following terms apply."}]
        results = detect_overrides(clauses)
        self.assertTrue(any(r["overridden_section"] == "8" for r in results))

    def test_detects_except_as_provided_in_with_section(self):
        clauses = [{"section_number": "6", "document_type": "SOW",
                    "text": "Except as provided in Section 12, all warranty terms apply."}]
        results = detect_overrides(clauses)
        self.assertTrue(any(r["overridden_section"] == "12" for r in results))

    def test_detects_subject_to_with_section(self):
        clauses = [{"section_number": "2", "document_type": "SOW",
                    "text": "Subject to Section 7 of the MSA, contractor may subcontract."}]
        results = detect_overrides(clauses)
        self.assertTrue(any(r["overridden_section"] == "7" for r in results))

    def test_subject_to_without_section_ref_not_flagged(self):
        # "Subject to applicable law" — no section reference — must not flag
        clauses = [{"section_number": "1", "document_type": "MSA",
                    "text": "Subject to applicable law and regulations."}]
        results = detect_overrides(clauses)
        self.assertEqual(results, [])

    def test_supersedes_without_section_not_flagged(self):
        # "supersedes all prior agreements" — no section ref — must not flag
        clauses = [{"section_number": "10", "document_type": "MSA",
                    "text": "This Agreement supersedes all prior written agreements between the parties."}]
        results = detect_overrides(clauses)
        self.assertEqual(results, [])

    def test_which_wins_present_on_named_section_override(self):
        clauses = [{"section_number": "7", "document_type": "SOW",
                    "text": "Notwithstanding MSA Section 8, liability is uncapped."}]
        results = detect_overrides(clauses)
        self.assertIn("which_wins", results[0])
        self.assertIn("8", results[0]["which_wins"])

    def test_which_wins_present_on_unnamed_override(self):
        clauses = [{"section_number": "9", "document_type": "SOW",
                    "text": "Notwithstanding anything to the contrary herein, this applies."}]
        results = detect_overrides(clauses)
        self.assertIn("which_wins", results[0])

    def test_matched_text_present(self):
        clauses = [{"section_number": "7", "document_type": "SOW",
                    "text": "Notwithstanding MSA Section 8, liability is uncapped."}]
        results = detect_overrides(clauses)
        self.assertIn("matched_text", results[0])
        self.assertTrue(len(results[0]["matched_text"]) > 0)


# ---------------------------------------------------------------------------
# Cross-document financial conflict detection
# ---------------------------------------------------------------------------

class TestCrossDocumentFinancialConflicts(unittest.TestCase):

    def _make_clauses(self, msa_text, sow_text, msa_sec="4", sow_sec="9"):
        return [
            {"section_number": msa_sec, "document_type": "MSA", "text": msa_text},
            {"section_number": sow_sec, "document_type": "SOW", "text": sow_text},
        ]

    def test_flags_sow_amount_exceeding_msa_cap(self):
        from financial_risk_detector import detect_cross_document_financial_conflicts
        clauses = self._make_clauses(
            "Liability shall not exceed $100,000 in aggregate.",
            "Total milestone payment is $250,000 upon delivery."
        )
        results = detect_cross_document_financial_conflicts(clauses)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "FINANCIAL_CLAUSE")
        self.assertEqual(results[0]["severity"], "HIGH")
        self.assertIn("which_wins", results[0])
        self.assertIn("msa_cap_amount", results[0])
        self.assertIn("sow_amount", results[0])

    def test_no_conflict_when_sow_below_cap(self):
        from financial_risk_detector import detect_cross_document_financial_conflicts
        clauses = self._make_clauses(
            "Liability capped at $500,000.",
            "Invoice total is $200,000."
        )
        results = detect_cross_document_financial_conflicts(clauses)
        self.assertEqual(results, [])

    def test_no_conflict_when_no_cap_language_in_msa(self):
        from financial_risk_detector import detect_cross_document_financial_conflicts
        clauses = self._make_clauses(
            "Payment due within 30 days of invoice receipt.",  # no cap language
            "Total contract value is $500,000."
        )
        results = detect_cross_document_financial_conflicts(clauses)
        self.assertEqual(results, [])

    def test_no_conflict_when_no_sow_amounts(self):
        from financial_risk_detector import detect_cross_document_financial_conflicts
        clauses = [
            {"section_number": "4", "document_type": "MSA",
             "text": "Liability shall not exceed $100,000."},
            {"section_number": "9", "document_type": "SOW",
             "text": "Deliverables must be completed on time."},  # no amounts
        ]
        results = detect_cross_document_financial_conflicts(clauses)
        self.assertEqual(results, [])

    def test_empty_clause_list(self):
        from financial_risk_detector import detect_cross_document_financial_conflicts
        self.assertEqual(detect_cross_document_financial_conflicts([]), [])

    def test_deduplicates_same_section_pair(self):
        from financial_risk_detector import detect_cross_document_financial_conflicts
        # Two SOW amounts in the same section vs one MSA cap — should produce one conflict
        clauses = [
            {"section_number": "4", "document_type": "MSA",
             "text": "Aggregate liability capped at $100,000."},
            {"section_number": "9", "document_type": "SOW",
             "text": "Phase 1: $200,000. Phase 2: $300,000."},
        ]
        results = detect_cross_document_financial_conflicts(clauses)
        self.assertEqual(len(results), 1)

    def test_conflict_has_description_mentioning_both_amounts(self):
        from financial_risk_detector import detect_cross_document_financial_conflicts
        clauses = self._make_clauses(
            "Maximum aggregate liability shall not exceed $100,000.",
            "Total contract value is $500,000."
        )
        results = detect_cross_document_financial_conflicts(clauses)
        self.assertEqual(len(results), 1)
        desc = results[0]["description"]
        self.assertIn("500,000", desc)
        self.assertIn("100,000", desc)


if __name__ == "__main__":
    unittest.main(verbosity=2)

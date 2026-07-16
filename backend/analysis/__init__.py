"""
Component 4 — Contradiction & Risk Detector

Given clause pairs (one from MSA, one from SOW) and the full clause list,
this package finds:
  1. AI-detected contradictions (contradiction_detector.py)
  2. "Notwithstanding ..." override language (override_detector.py)
  3. Financial / penalty clauses needing human review (financial_risk_detector.py)
  4. Ranks + IDs the combined risk list (risk_ranker.py)
"""

from .contradiction_detector import detect_contradiction, detect_all_contradictions
from .override_detector import detect_overrides
from .financial_risk_detector import detect_financial_risks, detect_cross_document_financial_conflicts
from .risk_ranker import rank_risks
from .risk_pipeline import run_risk_detection, normalize_risks
from .contractnli_evaluator import evaluate_against_contractnli

__all__ = [
    "detect_contradiction",
    "detect_all_contradictions",
    "detect_overrides",
    "detect_financial_risks",
    "detect_cross_document_financial_conflicts",
    "rank_risks",
    "run_risk_detection",   # <-- Component 6 should call this one function
    "normalize_risks",
    "evaluate_against_contractnli",  # <-- run standalone for the demo accuracy number
]

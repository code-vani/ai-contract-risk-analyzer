"""Real adapter — exposes the same 7-function interface as mock_pipeline
but routes through the actual Components 1-4 and the real database (C9).

Interface contract (must match mock_pipeline.py exactly):
  extract_smart(file_path)                       -> dict  (ExtractionResult)
  extract_clauses(extraction_result, doc_type)   -> list[dict]
  build_graph_json(all_clauses)                  -> dict  (GraphObject for Vis.js)
  detect_contradictions(all_clauses, graph_dict) -> list[dict]  (RiskObjects)
  save_analysis(record)                          -> int   (analysis_id)
  get_all_analyses()                             -> list[dict]
  get_analysis_by_id(analysis_id)               -> dict | None

Bridge notes
------------
* build_graph returns a NetworkX DiGraph, not a dict — we convert via graph_serializer.
* detect_contradictions in the mock accepted (all_clauses, graph_dict), but the real
  Component 4 needs clause_pairs from find_topic_pairs(). The graph_dict arg is
  accepted here but unused — pairs are derived directly from clauses, which is
  more reliable than parsing the serialised graph back.
"""

import sys
import os

# Ensure sibling backend packages are importable whether this file is executed
# directly or imported from pipeline.py (which sets cwd to backend/).
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# --------------------------------------------------------------------------
# Component 1 — re-export directly (same signature as mock)
# --------------------------------------------------------------------------
from ingestion.smart_extractor import extract_smart  # noqa: F401  (re-export)

# --------------------------------------------------------------------------
# Component 2 — re-export directly (same signature as mock)
# --------------------------------------------------------------------------
from ai.clause_extractor import extract_clauses  # noqa: F401  (re-export)

# --------------------------------------------------------------------------
# Component 3 — dependency graph
# --------------------------------------------------------------------------
from graph.graph_builder import build_graph
from graph.cycle_detector import find_cycles
from graph.graph_serializer import graph_to_json

# --------------------------------------------------------------------------
# Component 4 — contradiction / override / financial risk detection
# --------------------------------------------------------------------------
from graph.edge_analyzer import find_topic_pairs, tag_cross_document_edges
from analysis.risk_pipeline import run_risk_detection

# --------------------------------------------------------------------------
# Component 9 — audit trail database
# --------------------------------------------------------------------------
from database.db import save_analysis, get_all_analyses, get_analysis_by_id  # noqa: F401


# --------------------------------------------------------------------------
# Bridged implementations
# --------------------------------------------------------------------------

def build_graph_json(all_clauses: list) -> dict:
    """Build the NetworkX graph, detect cycles, and serialise to a Vis.js dict."""
    g = build_graph(all_clauses)
    cycles = find_cycles(g)
    tag_cross_document_edges(g)   # must run before serialization so edges get correct colour
    return graph_to_json(g, cycles, risks=None, hub_top_n=5)


def detect_contradictions(all_clauses: list, graph: dict) -> list:
    """
    Run the full Component 4 risk detection pipeline.

    The `graph` argument is kept for interface compatibility with the mock but is
    not used — we derive clause pairs directly from all_clauses via find_topic_pairs,
    which is more accurate than reconstructing pairs from the serialised graph dict.
    """
    clause_pairs = find_topic_pairs(all_clauses)
    return run_risk_detection(clause_pairs, all_clauses)

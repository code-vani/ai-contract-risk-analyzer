"""Component 6 — orchestration pipeline.

`run_analysis` chains the whole system: Components 1 -> 2 -> 3 -> 4 -> 5 -> 9.
Component 5 (redlines + missing docs) is this repo's real code; the rest come
through a single indirection point (`_C`) so that flipping `USE_MOCKS` — or, at
integration, editing the import below — swaps mocks for the teammates' real
modules without touching any other line.
"""

import config

# --- Single indirection point for teammate-owned components (1-4 & 9) -------
# At integration, replace this block with imports of the real modules that
# expose the same function names (extract_text, extract_clauses,
# build_graph_json, detect_contradictions, save_analysis, get_all_analyses,
# get_analysis_by_id).
if config.USE_MOCKS:
    if config.PIPELINE_SOURCE == "cuad":
        # Reads/parses the real uploaded file — for testing C5/C6 on real data.
        from mocks import cuad_pipeline as _C
    else:
        # Fixed demo data with the 6 built-in issues (deterministic demo).
        from mocks import mock_pipeline as _C
else:  # pragma: no cover - USE_MOCKS=False → route through real components
    from adapters import real_pipeline as _C

# --- Component 5 (this repo's real code) ------------------------------------
from output.missing_doc_detector import find_missing_documents
from output.output_formatter import format_output, summarize
from output.redline_generator import generate_redlines


def _normalize_graph(graph: dict) -> dict:
    """Normalise edge key to `edge_type` (some producers emit `type`)."""
    if not graph:
        return {"nodes": [], "edges": [], "circular_references": []}
    for edge in graph.get("edges", []):
        if "edge_type" not in edge and "type" in edge:
            edge["edge_type"] = edge.pop("type")
    graph.setdefault("nodes", [])
    graph.setdefault("edges", [])
    graph.setdefault("circular_references", [])
    return graph


def run_analysis(msa_path: str, sow_path: str, msa_name: str, sow_name: str) -> dict:
    """Run the full analysis for one MSA + SOW pair and return the result dict."""
    # 1. Component 1 — smart extraction -> ExtractionResult { mode, content, ... }.
    msa_extraction = _C.extract_smart(msa_path)
    sow_extraction = _C.extract_smart(sow_path)
    for name, extraction in ((msa_name, msa_extraction), (sow_name, sow_extraction)):
        if extraction.get("mode") == "error":
            raise ValueError(f"Could not extract '{name}': {extraction.get('error')}")

    # 2. Component 2 — extract clauses from each ExtractionResult.
    msa_clauses = _C.extract_clauses(msa_extraction, "MSA")
    sow_clauses = _C.extract_clauses(sow_extraction, "SOW")
    all_clauses = list(msa_clauses) + list(sow_clauses)

    # 3. Component 3 — dependency graph (+ circular references).
    graph = _normalize_graph(_C.build_graph_json(all_clauses))

    # 4. Component 4 — contradiction / override / risk detection.
    risks = _C.detect_contradictions(all_clauses, graph)

    # 5. Component 5 — redlines + missing-document refusals (this repo).
    risks_with_redlines = generate_redlines(risks)
    missing_docs = find_missing_documents(all_clauses, [msa_name, sow_name])
    results = format_output(risks_with_redlines, missing_docs)
    summary = summarize(results)

    # 6. Component 9 — persist the audit trail.
    record = {
        "msa_filename": msa_name,
        "sow_filename": sow_name,
        "total_risks":   summary["total"],
        "blocker_count": summary["blocker"],
        "critical_count": summary["critical"],
        "high_count":    summary["high"],
        "medium_count":  summary["medium"],
        "low_count":     summary["low"],
        "status": "COMPLETE",
        "results": results,
        "clauses": all_clauses,
        "graph": graph,
    }
    analysis_id = _C.save_analysis(record)

    return {
        "analysis_id": analysis_id,
        "summary": summary,
        "results": results,
        "risks": risks_with_redlines,
        "missing_docs": missing_docs,
        "graph": graph,
    }


# --- History passthroughs (Component 9 via the indirection point) -----------

def list_history() -> list[dict]:
    return _C.get_all_analyses()


def get_history(analysis_id: int) -> dict | None:
    return _C.get_analysis_by_id(analysis_id)

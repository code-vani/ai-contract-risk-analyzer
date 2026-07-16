"""Mock stubs for the teammate-owned components (1-4 & 9) — Option A.

Each function mirrors the interface Component 6's pipeline expects and returns
data in the agreed formats (see `sample_payloads`). They ignore their inputs and
return canned payloads, which is enough to run and demo `POST /upload`
standalone. At integration, `pipeline.py` points its imports at the real modules
instead of this file — no other code changes.

The in-memory `_STORE` fakes Component 9's database (save/load).
"""

from datetime import datetime, timezone

from mocks import sample_payloads

# Fake DB: analysis_id -> full analysis record.
_STORE: dict[int, dict] = {}
_NEXT_ID = 1


# --- Component 1: smart extraction (v2) ------------------------------------

def extract_smart(file_path: str) -> dict:
    """Return a canned ExtractionResult (text mode) regardless of the file.

    Mirrors the v2 Component 1 output shape: { mode, content, file_type,
    word_count, page_count, words_per_page }.
    """
    content = "## Sample Contract\n\nMock extraction content for standalone runs."
    words = len(content.split())
    return {
        "mode": "text",
        "content": content,
        "file_type": "pdf",
        "word_count": words,
        "page_count": 1,
        "words_per_page": words,
    }


# --- Component 2: clause extraction (v2 — reads ExtractionResult) -----------

def extract_clauses(extraction_result: dict, document_type: str) -> list[dict]:
    """Return the canned clause list for the given document type.

    Accepts the ExtractionResult dict from Component 1 (v2). The mock ignores its
    content and keys off document_type only.
    """
    if extraction_result.get("mode") == "error":
        return []
    if document_type == "MSA":
        return [dict(c) for c in sample_payloads.MSA_CLAUSES]
    return [dict(c) for c in sample_payloads.SOW_CLAUSES]


# --- Component 3: dependency graph -----------------------------------------

def build_graph_json(all_clauses: list[dict]) -> dict:
    """Return the canned GraphObject (nodes, edges, circular_references)."""
    return {
        "nodes": [dict(n) for n in sample_payloads.GRAPH["nodes"]],
        "edges": [dict(e) for e in sample_payloads.GRAPH["edges"]],
        "circular_references": [dict(c) for c in sample_payloads.GRAPH["circular_references"]],
    }


# --- Component 4: contradiction detection ----------------------------------

def detect_contradictions(all_clauses: list[dict], graph: dict) -> list[dict]:
    """Return the canned risk list (contradictions + overrides)."""
    return [dict(r) for r in sample_payloads.RISKS]


# --- Component 9: audit trail / database ------------------------------------

def save_analysis(record: dict) -> int:
    """Persist a completed analysis in memory and return its id."""
    global _NEXT_ID
    analysis_id = _NEXT_ID
    _NEXT_ID += 1
    stored = dict(record)
    stored["id"] = analysis_id
    stored.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    _STORE[analysis_id] = stored
    return analysis_id


def get_all_analyses() -> list[dict]:
    """Return summary rows for every saved analysis (no clause/risk detail)."""
    summaries = []
    for a in _STORE.values():
        summaries.append(
            {
                "id": a["id"],
                "timestamp": a.get("timestamp"),
                "msa_filename": a.get("msa_filename"),
                "sow_filename": a.get("sow_filename"),
                "total_risks": a.get("total_risks", 0),
                "blocker_count": a.get("blocker_count", 0),
                "critical_count": a.get("critical_count", 0),
                "high_count": a.get("high_count", 0),
                "medium_count": a.get("medium_count", 0),
                "low_count": a.get("low_count", 0),
                "status": a.get("status", "COMPLETE"),
            }
        )
    return sorted(summaries, key=lambda s: s["id"], reverse=True)


def get_analysis_by_id(analysis_id: int) -> dict | None:
    """Return the full stored analysis, or None if the id is unknown."""
    return _STORE.get(analysis_id)

"""Dataset-backed pipeline stub — lets you test C5 & C6 on REAL contract text.

Unlike `mock_pipeline` (which returns fixed canned data), this stub actually
reads the uploaded file, splits its real text into clauses, and derives simple
risks from that text — so `POST /upload` exercises the real Component 5 code on
real CUAD contract content, end-to-end through the server.

IMPORTANT: this is NOT the teammates' real C1-C4. The clause splitter and risk
finder here are deliberate lightweight heuristics, used only so you can watch
Components 5 & 6 operate on real dataset text before integration. Enable it with
    USE_MOCKS=true  PIPELINE_SOURCE=cuad
"""

import os
import re
from datetime import datetime, timezone

_STORE: dict[int, dict] = {}
_NEXT_ID = 1

# Regex for section-style headings found in real contracts.
_HEADING = re.compile(
    r"(?im)^\s*(?:section|article)?\s*(\d+(?:\.\d+)?)[.\s\-—:]"
)


# --- Component 1 stand-in: read the real file -------------------------------

def extract_smart(file_path: str) -> dict:
    """Read the uploaded file's real text into an ExtractionResult."""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            content = "\n".join(page.get_text() for page in doc)
            pages = len(doc)
        else:  # .txt / .docx-as-text fallback
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            pages = max(1, content.count("\f") + 1)
    except Exception as exc:
        return {"mode": "error", "content": None, "error": str(exc)}

    words = len(content.split())
    return {
        "mode": "text",
        "content": content,
        "file_type": ext.lstrip("."),
        "word_count": words,
        "page_count": pages,
        "words_per_page": words // pages if pages else words,
    }


# --- Component 2 stand-in: split real text into clauses ----------------------

def extract_clauses(extraction_result: dict, document_type: str) -> list[dict]:
    """Split the real contract text into rough clause objects."""
    if extraction_result.get("mode") == "error":
        return []
    text = extraction_result.get("content", "") or ""

    clauses: list[dict] = []
    matches = list(_HEADING.finditer(text))
    if len(matches) >= 3:
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = " ".join(text[start:end].split())[:600]
            clauses.append(_clause(m.group(1), body, document_type, i + 1))
    else:
        # Fallback: chunk into ~500-char paragraphs, numbered sequentially.
        chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
        for i, chunk in enumerate(chunks[:40], start=1):
            clauses.append(_clause(str(i), " ".join(chunk.split())[:600], document_type, i))

    return clauses


def _clause(section: str, body: str, doc_type: str, page: int) -> dict:
    title = body[:50].rsplit(" ", 1)[0] if body else f"Clause {section}"
    return {
        "section_number": section,
        "title": title,
        "text": body,
        "document_type": doc_type,
        "page_number": page,
        "references_to": [],
        "clause_type": "general",
    }


# --- Component 4 stand-in: derive simple risks from real clauses -------------

_MAX_RISKS = 4  # keep small — each HIGH/MEDIUM risk triggers one Gemini call

def detect_contradictions(all_clauses: list[dict], graph: dict) -> list[dict]:
    """Flag a few real clauses as risks so C5 can redline actual contract text."""
    risks: list[dict] = []
    for clause in all_clauses:
        text = clause["text"]
        sect = f"{clause['document_type']}-{clause['section_number']}"

        if re.search(r"\bnotwithstanding\b", text, re.IGNORECASE):
            risks.append(_risk("OVERRIDE", "HIGH", sect, text,
                               "Override language ('Notwithstanding') silently supersedes another clause."))
        elif re.search(r"\b(?:seven|thirty|forty-five|sixty|ninety|\d+)\b[^.]{0,40}\bdays\b", text, re.IGNORECASE):
            risks.append(_risk("TERM", "MEDIUM", sect, text,
                               "Time period clause — verify it aligns with the governing agreement."))

        if len(risks) >= _MAX_RISKS:
            break

    for i, r in enumerate(risks, start=1):
        r["risk_id"] = f"RISK-{i:03d}"
    return risks


def _risk(rtype: str, severity: str, section: str, text: str, description: str) -> dict:
    return {
        "risk_id": "",
        "type": rtype,
        "severity": severity,
        "clause_a_section": section,
        "clause_b_section": "",
        "description": description,
        "original_text": text,
        "suggested_text": "",
        "change_summary": "",
        "confidence": 0.7,
    }


# --- Component 3 stand-in: minimal graph ------------------------------------

def build_graph_json(all_clauses: list[dict]) -> dict:
    nodes = [
        {
            "id": f"{c['document_type']}-{c['section_number']}",
            "label": f"{c['document_type']} § {c['section_number']}",
            "title": c["title"],
            "document_type": c["document_type"],
            "text": c["text"],
        }
        for c in all_clauses
    ]
    return {"nodes": nodes, "edges": [], "circular_references": []}


# --- Component 9 stand-in: in-memory store ----------------------------------

def save_analysis(record: dict) -> int:
    global _NEXT_ID
    analysis_id = _NEXT_ID
    _NEXT_ID += 1
    stored = dict(record)
    stored["id"] = analysis_id
    stored.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    _STORE[analysis_id] = stored
    return analysis_id


def get_all_analyses() -> list[dict]:
    return sorted(
        (
            {
                "id": a["id"], "timestamp": a.get("timestamp"),
                "msa_filename": a.get("msa_filename"), "sow_filename": a.get("sow_filename"),
                "total_risks": a.get("total_risks", 0),
                "blocker_count": a.get("blocker_count", 0),
                "critical_count": a.get("critical_count", 0),
                "high_count": a.get("high_count", 0),
                "medium_count": a.get("medium_count", 0), "low_count": a.get("low_count", 0),
                "status": a.get("status", "COMPLETE"),
            }
            for a in _STORE.values()
        ),
        key=lambda s: s["id"], reverse=True,
    )


def get_analysis_by_id(analysis_id: int) -> dict | None:
    return _STORE.get(analysis_id)

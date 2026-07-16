"""
Hybrid clause extractor — no Gemini API needed for structured contracts.

Replaces the Gemini call in Component 2 for documents that have clear
section headings. Falls back to Gemini automatically for unstructured docs.

Pipeline:
  1. Regex   → split at headings → section_number + title + text
  2. LEDGAR  → sklearn classifier → clause_type  (instant, no API)
  3. Regex   → find_references   → references_to (already existed)
  4. Keyword → obligation check  → has_obligation
"""

import os
import pickle
import re

from ai.reference_finder import find_references, remove_self_references

# ── Paths ─────────────────────────────────────────────────────────────────────

MODEL_PATH = os.path.join(os.path.dirname(__file__), "ledgar_classifier.pkl")

# ── Regexes ───────────────────────────────────────────────────────────────────

# Detects section heading start (same pattern used in clause_extractor.py)
_SECTION_HEADING = re.compile(
    r"(?m)^(?=#{1,4}\s|\d{1,2}\.\s|\bArticle\s+[IVXLC\d]+|\bSection\s+\d)",
)

# Parses a heading line to extract (section_number, title)
# Handles: "## 4.1 Payment Terms", "4.1. Payment Terms", "Article IV - Confidentiality"
_HEADING_PARSE = re.compile(
    r"^(?:#{1,4}\s+)?"                                    # strip markdown #
    r"(?:(?:Article|Section|Clause)\s+)?"                 # strip keyword prefix
    r"(\d{1,2}(?:\.\d{1,3})*|[IVXLC]{1,7})"             # capture section number
    r"[\s\.\:\-–—]+"                            # separator (dash variants too)
    r"(.{2,120}?)\s*$",                                   # capture title
    re.IGNORECASE,
)

# Obligation keywords — presence → has_obligation: true
_OBLIGATION_RE = re.compile(
    r"\b("
    r"shall|must"
    r"|will\s+(?:provide|ensure|deliver|maintain|notify|indemnify|pay|obtain)"
    r"|agrees?\s+to|agree\s+that"
    r"|is\s+required\s+to|are\s+required\s+to"
    r"|undertakes?\s+to|covenants?\s+to"
    r"|is\s+obligated\s+to|are\s+obligated\s+to"
    r"|warrants?\s+(?:that|to)"
    r")\b",
    re.IGNORECASE,
)

# Minimum heading count to treat a document as structured
_MIN_HEADINGS = 3

# ── Lazy model loader ─────────────────────────────────────────────────────────

_classifier = None


def _load_classifier():
    global _classifier
    if _classifier is not None:
        return _classifier
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            _classifier = pickle.load(f)
        print("[Hybrid] LEDGAR classifier loaded from disk")
        return _classifier
    except Exception as exc:
        print(f"[Hybrid] WARNING: Could not load classifier — {exc}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def is_structured(text: str) -> bool:
    """
    Return True if the document has enough section headings for regex parsing.
    Unstructured docs (no headings, plain paragraphs) go to Gemini instead.
    """
    return len(_SECTION_HEADING.findall(text)) >= _MIN_HEADINGS


def extract_clauses_hybrid(text: str, document_type: str) -> list[dict]:
    """
    Extract and classify all clauses without any API call.

    Returns the same schema as the Gemini path so downstream components
    (C3 graph, C4 risk detector) work identically:

        [{
            section_number, title, text, document_type,
            clause_type, references_to, has_obligation
        }]

    Returns an empty list if the model is not trained yet — caller should
    fall back to Gemini in that case.
    """
    clf = _load_classifier()
    if clf is None:
        print("[Hybrid] No trained model found — run ai/train_ledgar_classifier.py first")
        return []

    sections = _split_sections(text)
    if not sections:
        return []

    # Batch predict clause types for all sections in one call (fast)
    raw_texts = [s["raw_text"] for s in sections]
    try:
        clause_types = clf.predict(raw_texts).tolist()
    except Exception as exc:
        print(f"[Hybrid] Classifier predict failed: {exc}")
        clause_types = ["other"] * len(sections)

    clauses = []
    seen = set()

    for section, clause_type in zip(sections, clause_types):
        sec_num  = section["section_number"]
        raw_text = section["raw_text"].strip()

        if sec_num in seen or len(raw_text) < 20:
            continue
        seen.add(sec_num)

        refs = remove_self_references(find_references(raw_text), sec_num)

        clauses.append({
            "section_number": sec_num,
            "title":          section["title"],
            "text":           raw_text,
            "document_type":  document_type,
            "clause_type":    clause_type,
            "references_to":  refs,
            "has_obligation": bool(_OBLIGATION_RE.search(raw_text)),
        })

    print(f"[Hybrid] Extracted {len(clauses)} clauses (0 API calls)")
    return clauses


# ── Internal helpers ──────────────────────────────────────────────────────────

def _split_sections(text: str) -> list[dict]:
    """
    Split text at section headings. Returns raw section dicts:
        [{ section_number, title, raw_text }]
    """
    split_points = [m.start() for m in _SECTION_HEADING.finditer(text)]

    if not split_points:
        return [{"section_number": "PREAMBLE", "title": "Agreement", "raw_text": text.strip()}]

    sections = []
    for i, start in enumerate(split_points):
        end   = split_points[i + 1] if i + 1 < len(split_points) else len(text)
        block = text[start:end].strip()
        if not block:
            continue

        lines        = block.split("\n", 1)
        heading_line = lines[0]
        body         = lines[1].strip() if len(lines) > 1 else ""

        sec_num, title = _parse_heading(heading_line)
        sections.append({
            "section_number": sec_num,
            "title":          title,
            "raw_text":       body or block,
        })

    return sections


def _parse_heading(line: str) -> tuple[str, str]:
    """
    Parse a heading line → (section_number, title).
    Falls back gracefully when the format is unusual.
    """
    clean = re.sub(r"^#{1,4}\s+", "", line.strip())
    m = _HEADING_PARSE.match(clean)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # No numeric/roman section number — use full line as title
    title = clean[:80] if clean else "Preamble"
    return "PREAMBLE", title

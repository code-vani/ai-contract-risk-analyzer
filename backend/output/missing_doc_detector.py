"""Component 5, Task 3 — missing-document refusal detection.

When a clause references an external document (e.g. "Schedule 1", "Exhibit A")
that was not among the uploaded files, we refuse to evaluate that clause rather
than guessing. This produces a BLOCKER refusal object for the frontend.
"""

import re

# Patterns for external-document references, most-specific label first.
_REFERENCE_PATTERNS = [
    re.compile(r"\bExhibit\s+([A-Z])\b", re.IGNORECASE),
    re.compile(r"\bSchedule\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\bAppendix\s+([A-Z])\b", re.IGNORECASE),
    re.compile(r"\bAttachment\s+([A-Z0-9])\b", re.IGNORECASE),
    re.compile(r"\bAnnex\s+([A-Z0-9])\b", re.IGNORECASE),
]


def _reference_present(reference: str, uploaded_filenames: list[str]) -> bool:
    """True if the referenced document appears to be among the uploaded files.

    Matches loosely: "Schedule 1" is considered provided if a filename contains
    both the label ("schedule") and identifier ("1"), e.g. "Schedule_1.pdf".
    """
    label, _, identifier = reference.partition(" ")
    label = label.lower()
    identifier = identifier.strip().lower()
    for name in uploaded_filenames:
        low = name.lower()
        if label in low and (not identifier or identifier in low):
            return True
    return False


def find_missing_documents(clauses: list[dict], uploaded_filenames: list[str]) -> list[dict]:
    """Return MISSING_DOCUMENT refusal objects for un-provided referenced docs.

    Scans each clause's text for external-document references and, for any not
    found among `uploaded_filenames`, emits a BLOCKER refusal. De-duplicates on
    (clause_section, referenced_document).
    """
    refusals: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for clause in clauses:
        text = clause.get("text", "") or ""
        doc_type = clause.get("document_type", "")
        section = clause.get("section_number", "")
        clause_section = f"{doc_type}-{section}" if doc_type else section

        for pattern in _REFERENCE_PATTERNS:
            for match in pattern.finditer(text):
                # Normalise label casing: "Schedule 1", "Exhibit A".
                label = match.group(0).split()[0].capitalize()
                identifier = match.group(1).upper()
                reference = f"{label} {identifier}"

                if _reference_present(reference, uploaded_filenames):
                    continue

                key = (clause_section, reference)
                if key in seen:
                    continue
                seen.add(key)

                # Prefer a fuller document name if the clause spells one out,
                # e.g. "Schedule 1 - Project Scope Document".
                referenced_document = _full_document_name(text, reference)

                refusals.append(
                    {
                        "type": "MISSING_DOCUMENT",
                        "severity": "BLOCKER",
                        "clause_section": clause_section,
                        "referenced_document": referenced_document,
                        "message": (
                            f"Cannot evaluate {doc_type} § {section} — "
                            f"{referenced_document} was not uploaded. Please provide "
                            f"this document to complete the analysis."
                        ),
                        "affected_clause_text": text,
                    }
                )

    return refusals


def _full_document_name(text: str, reference: str) -> str:
    """Return the reference plus any trailing descriptive name in the clause.

    e.g. "Schedule 1 - Project Scope Document" instead of just "Schedule 1".
    """
    m = re.search(
        re.escape(reference) + r"\s*[-–—]\s*([A-Z][\w ]+?)(?=[.,;]|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        return f"{reference} – {m.group(1).strip()}"
    return reference

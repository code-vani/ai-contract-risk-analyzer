"""Canned data reproducing the demo's built-in issues, in the agreed formats.

These payloads let Component 6's /upload run end-to-end without the real
Components 1-4 & 9. They mirror the crafted Sample_MSA / Sample_SOW so the
pipeline surfaces the same six issues the demo relies on:

    1. CONTRADICTION  payment 30 days (MSA 4.1) vs 45 days (SOW 2.2)   HIGH
    2. MISSING_DOCUMENT  Schedule 1 referenced by SOW 3.1              BLOCKER
    3. CIRCULAR_REFERENCE  SOW 5 <-> SOW 9                             CRITICAL
    4. OVERRIDE  IP ownership (SOW 6 "Notwithstanding MSA 5")          HIGH
    5. OVERRIDE  liability cap (SOW 7 "Notwithstanding MSA 7")         HIGH
    6. CONTRADICTION  termination 30 days (MSA 8.1) vs 7 days (SOW 8)  HIGH

Note on ownership of each issue at runtime:
    - Issues 1, 4, 5, 6 arrive as RISKS (mock Component 4 output).
    - Issue 3 lives in the GRAPH's circular_references (mock Component 3).
    - Issue 2 is produced by the REAL Component 5 (missing_doc_detector) from
      the SOW-3.1 clause text below, so it is intentionally NOT pre-baked here.
"""

# --- ClauseObjects (agreed format) -----------------------------------------

MSA_CLAUSES = [
    {
        "section_number": "4.1",
        "title": "Payment Terms",
        "text": "All invoices shall be paid within thirty (30) days of receipt.",
        "document_type": "MSA",
        "page_number": 4,
        "references_to": [],
        "clause_type": "payment",
    },
    {
        "section_number": "5",
        "title": "Intellectual Property",
        "text": "All work product created under this agreement is owned by the Client.",
        "document_type": "MSA",
        "page_number": 5,
        "references_to": [],
        "clause_type": "ip",
    },
    {
        "section_number": "7.1",
        "title": "Liability",
        "text": (
            "Total liability of either party shall not exceed the total value of "
            "the contract."
        ),
        "document_type": "MSA",
        "page_number": 7,
        "references_to": [],
        "clause_type": "liability",
    },
    {
        "section_number": "8.1",
        "title": "Termination",
        "text": (
            "Either party may terminate this agreement with thirty (30) days "
            "written notice."
        ),
        "document_type": "MSA",
        "page_number": 8,
        "references_to": [],
        "clause_type": "termination",
    },
]

SOW_CLAUSES = [
    {
        "section_number": "2.2",
        "title": "Payment Schedule",
        "text": (
            "All milestone payments are due within forty-five (45) days of invoice."
        ),
        "document_type": "SOW",
        "page_number": 2,
        "references_to": ["4.1"],
        "clause_type": "payment",
    },
    {
        "section_number": "3.1",
        "title": "Deliverables",
        "text": (
            "Deliverables are as specified in Schedule 1 - Project Scope Document."
        ),
        "document_type": "SOW",
        "page_number": 3,
        "references_to": [],
        "clause_type": "deliverables",
    },
    {
        "section_number": "5",
        "title": "Penalties",
        "text": "Late delivery penalties are as defined in Section 9.",
        "document_type": "SOW",
        "page_number": 5,
        "references_to": ["9"],
        "clause_type": "penalty",
    },
    {
        "section_number": "6",
        "title": "Intellectual Property",
        "text": (
            "Notwithstanding MSA Section 5, all developed code remains property of "
            "the Vendor for a period of 6 months post-delivery."
        ),
        "document_type": "SOW",
        "page_number": 6,
        "references_to": ["5"],
        "clause_type": "ip",
    },
    {
        "section_number": "7",
        "title": "Liability",
        "text": (
            "Notwithstanding MSA Section 7, liability for data breaches shall be "
            "uncapped."
        ),
        "document_type": "SOW",
        "page_number": 7,
        "references_to": ["7"],
        "clause_type": "liability",
    },
    {
        "section_number": "8",
        "title": "Termination",
        "text": "Either party may terminate this SOW with seven (7) days notice.",
        "document_type": "SOW",
        "page_number": 8,
        "references_to": ["8.1"],
        "clause_type": "termination",
    },
    {
        "section_number": "9",
        "title": "Penalty Amounts",
        "text": "Penalty amounts are determined based on Section 5 of this SOW.",
        "document_type": "SOW",
        "page_number": 9,
        "references_to": ["5"],
        "clause_type": "penalty",
    },
]

ALL_CLAUSES = MSA_CLAUSES + SOW_CLAUSES


# --- RiskObjects (agreed format; mock Component 4 output) -------------------
# suggested_text / change_summary are left blank on purpose: the real
# Component 5 redline generator fills them in.

RISKS = [
    {
        "risk_id": "RISK-001",
        "type": "CONTRADICTION",
        "severity": "HIGH",
        "clause_a_section": "MSA-4.1",
        "clause_b_section": "SOW-2.2",
        "description": (
            "Payment term conflict: SOW specifies a 45-day window vs MSA's 30-day "
            "requirement."
        ),
        "original_text": "All milestone payments are due within forty-five (45) days of invoice.",
        "suggested_text": "",
        "change_summary": "",
        "confidence": 0.95,
    },
    {
        "risk_id": "RISK-002",
        "type": "OVERRIDE",
        "severity": "HIGH",
        "clause_a_section": "SOW-6",
        "clause_b_section": "MSA-5",
        "description": (
            "SOW Section 6 silently overrides MSA Section 5 on IP ownership via a "
            "'Notwithstanding' clause."
        ),
        "original_text": (
            "Notwithstanding MSA Section 5, all developed code remains property of "
            "the Vendor for a period of 6 months post-delivery."
        ),
        "suggested_text": "",
        "change_summary": "",
        "confidence": 0.9,
    },
    {
        "risk_id": "RISK-003",
        "type": "OVERRIDE",
        "severity": "HIGH",
        "clause_a_section": "SOW-7",
        "clause_b_section": "MSA-7.1",
        "description": (
            "SOW Section 7 silently overrides MSA Section 7 liability cap, making "
            "data-breach liability uncapped."
        ),
        "original_text": (
            "Notwithstanding MSA Section 7, liability for data breaches shall be "
            "uncapped."
        ),
        "suggested_text": "",
        "change_summary": "",
        "confidence": 0.92,
    },
    {
        "risk_id": "RISK-004",
        "type": "CONTRADICTION",
        "severity": "HIGH",
        "clause_a_section": "MSA-8.1",
        "clause_b_section": "SOW-8",
        "description": (
            "Termination notice conflict: SOW allows 7-day notice vs MSA's 30-day "
            "requirement."
        ),
        "original_text": "Either party may terminate this SOW with seven (7) days notice.",
        "suggested_text": "",
        "change_summary": "",
        "confidence": 0.94,
    },
]


# --- GraphObject (agreed format; mock Component 3 output) -------------------

def _node(clause):
    return {
        "id": f"{clause['document_type']}-{clause['section_number']}",
        "label": f"{clause['document_type']} § {clause['section_number']}",
        "title": clause["title"],
        "document_type": clause["document_type"],
        "text": clause["text"],
    }


GRAPH = {
    "nodes": [_node(c) for c in ALL_CLAUSES],
    "edges": [
        {"from": "SOW-2.2", "to": "MSA-4.1", "edge_type": "contradiction"},
        {"from": "SOW-6", "to": "MSA-5", "edge_type": "cross_document"},
        {"from": "SOW-7", "to": "MSA-7.1", "edge_type": "cross_document"},
        {"from": "SOW-8", "to": "MSA-8.1", "edge_type": "contradiction"},
        {"from": "SOW-5", "to": "SOW-9", "edge_type": "circular"},
        {"from": "SOW-9", "to": "SOW-5", "edge_type": "circular"},
    ],
    "circular_references": [
        {
            "cycle_path": ["SOW-5", "SOW-9", "SOW-5"],
            "severity": "CRITICAL",
            "description": (
                "SOW § 5 and SOW § 9 reference each other, creating an "
                "unresolvable loop that makes both clauses unenforceable."
            ),
        }
    ],
}

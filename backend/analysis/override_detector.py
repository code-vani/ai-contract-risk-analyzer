"""
override_detector.py — Task 2

Pure pattern matching, no AI call needed — these are deterministic text
patterns where an LLM would only add latency and hallucination risk.

Handles five common contract override/modification phrases:
  1. "Notwithstanding [Section X]" / "Notwithstanding anything to the contrary"
  2. "Supersedes [Section X]" / "Superseding [Section X]"
  3. "In lieu of [Section X]"
  4. "Except as provided/set forth/specified in [Section X]"
  5. "Subject to [Section X]" (only when a section number follows immediately)

Each match produces an OVERRIDE risk with a deterministic `which_wins`
field, so downstream components (Component 5 redlines, Component 6 API)
get a consistent shape regardless of which phrase triggered the flag.
"""

import re

SECTION_REF_PATTERN = re.compile(
    r"(?:Section|Sec\.?|§|Clause|Article)\s*([0-9]+(?:\.[0-9]+)*)",
    re.IGNORECASE,
)

LOOKAHEAD_WINDOW = 80  # chars after the trigger phrase to search for a section ref

# Each tuple: (compiled trigger regex, human-readable label, require_section_ref)
# require_section_ref=False → flag even when no specific section is named
#   (e.g. "Notwithstanding anything to the contrary" is a real override)
# require_section_ref=True  → skip if no section number found in the window
#   (avoids false positives like "supersedes all prior agreements")
OVERRIDE_TRIGGERS = [
    (
        re.compile(r"Notwithstanding\b", re.IGNORECASE),
        "notwithstanding override",
        False,
    ),
    (
        re.compile(r"\b(?:supersedes?|superseding)\b", re.IGNORECASE),
        "supersession",
        True,
    ),
    (
        re.compile(r"\bIn\s+lieu\s+of\b", re.IGNORECASE),
        "in-lieu substitution",
        True,
    ),
    (
        re.compile(
            r"\bExcept\s+as\s+(?:provided|set\s+forth|specified)\s+in\b",
            re.IGNORECASE,
        ),
        "exception clause",
        True,
    ),
    # "Subject to Section X" only — requires the section keyword to follow
    # within the trigger itself so loose uses ("subject to applicable law")
    # never fire.
    (
        re.compile(
            r"\bSubject\s+to\s+(?:the\s+(?:terms|provisions)\s+of\s+)?"
            r"(?=(?:Section|§|Clause|Article)\b)",
            re.IGNORECASE,
        ),
        "subject-to limitation",
        True,
    ),
]


def _find_overridden_section(text: str, start_idx: int) -> str | None:
    """Search the window of text right after a trigger phrase for a section number."""
    window = text[start_idx: start_idx + LOOKAHEAD_WINDOW]
    match = SECTION_REF_PATTERN.search(window)
    return match.group(1) if match else None


def detect_overrides(clauses: list[dict]) -> list[dict]:
    """
    Scans each clause's text for override/modification language and returns
    a list of OVERRIDE risk objects, each with `which_wins` and `matched_text`.

    Handles clauses with zero, one, or multiple trigger phrases. Clauses with
    missing/empty text or section_number are skipped safely.
    """
    if not clauses:
        return []

    overrides = []

    for clause in clauses:
        text = (clause or {}).get("text", "") or ""
        section = (clause or {}).get("section_number", "UNKNOWN")
        doc_type = (clause or {}).get("document_type", "UNKNOWN")

        if not text.strip():
            continue

        for trigger_pattern, trigger_label, require_section_ref in OVERRIDE_TRIGGERS:
            for match in trigger_pattern.finditer(text):
                start_idx = match.start()
                overridden_section = _find_overridden_section(text, start_idx)

                if require_section_ref and not overridden_section:
                    continue

                snippet_start = max(0, start_idx - 10)
                snippet_end = min(len(text), start_idx + LOOKAHEAD_WINDOW)
                snippet = text[snippet_start:snippet_end].strip()

                if overridden_section:
                    description = (
                        f"{doc_type} § {section} contains {trigger_label} "
                        f"pointing at Section {overridden_section}: \"...{snippet}...\""
                    )
                    which_wins = (
                        f"{doc_type} § {section} controls — this clause explicitly "
                        f"overrides or modifies Section {overridden_section}."
                    )
                else:
                    description = (
                        f"{doc_type} § {section} contains general {trigger_label} "
                        f"(no specific section named): \"...{snippet}...\""
                    )
                    which_wins = (
                        f"{doc_type} § {section} controls — general override language "
                        f"supersedes any conflicting provisions in the paired document."
                    )

                overrides.append({
                    "type": "OVERRIDE",
                    "severity": "HIGH",
                    "overriding_clause_section": section,
                    "overriding_document_type": doc_type,
                    "overridden_section": overridden_section,
                    "description": description,
                    "which_wins": which_wins,
                    "clause_text": text,
                    "matched_text": f"...{snippet}...",
                    # Backward-compat aliases for teammates who coded against the
                    # breakdown doc's sample field names instead of this file's.
                    "overriding_section": section,
                    "overriding_document": doc_type,
                })

    return overrides


if __name__ == "__main__":
    import json

    test_clauses = [
        {
            "section_number": "7",
            "document_type": "SOW",
            "text": "Notwithstanding MSA Section 8, liability under this SOW shall be uncapped.",
        },
        {
            "section_number": "9",
            "document_type": "SOW",
            "text": "Notwithstanding anything to the contrary herein, delivery may be delayed.",
        },
        {
            "section_number": "3",
            "document_type": "SOW",
            "text": "This SOW supersedes Section 4 of the MSA for all delivery obligations.",
        },
        {
            "section_number": "5",
            "document_type": "SOW",
            "text": "In lieu of Section 12, the following warranty terms apply exclusively.",
        },
        {
            "section_number": "6",
            "document_type": "SOW",
            "text": "Except as provided in Section 3.2, all IP vests with the client.",
        },
        {
            "section_number": "2",
            "document_type": "SOW",
            "text": "Subject to Section 7 of the MSA, the contractor may subcontract work.",
        },
        {
            "section_number": "11",
            "document_type": "MSA",
            "text": "This Agreement supersedes all prior written agreements between the parties.",
        },
        {
            "section_number": "1",
            "document_type": "MSA",
            "text": "Subject to applicable law and regulatory requirements.",
        },
        {
            "section_number": "99",
            "document_type": "SOW",
            "text": "",
        },
    ]
    print(json.dumps(detect_overrides(test_clauses), indent=2))

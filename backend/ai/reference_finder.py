import re

# Numeric section references — e.g. "Section 4.1", "Clause 3", "§ 8.2"
_SECTION_PATTERNS = [
    re.compile(r"[Ss]ection\s+([\d\.]+(?:\([a-z]\))?)"),
    re.compile(r"[Cc]lause\s+([\d\.]+(?:\([a-z]\))?)"),
    re.compile(r"[Aa]rticle\s+([\d\.]+(?:\([a-z]\))?)"),
    re.compile(r"§\s*([\d\.]+(?:\([a-z]\))?)"),
    re.compile(r"[Pp]aragraph\s+([\d\.]+(?:\([a-z]\))?)"),
]

# Named document references — keep the full "Exhibit A" not just "A"
_DOC_PATTERNS = [
    re.compile(r"([Ss]chedule\s+[A-Z0-9]+)"),
    re.compile(r"([Ee]xhibit\s+[A-Z0-9]+)"),
    re.compile(r"([Aa]ppendix\s+[A-Z0-9]+)"),
    re.compile(r"([Aa]nnex\s+[A-Z0-9]+)"),
]


def find_references(text: str) -> list:
    """
    Scan clause text for cross-references to other sections/exhibits.
    Returns cleaned, unique list — no self-references, no trailing periods.
    e.g. "See Section 4.1 and Exhibit A" → ["4.1", "Exhibit A"]
    """
    found = set()

    for pattern in _SECTION_PATTERNS:
        for match in pattern.finditer(text):
            ref = match.group(1).strip().rstrip(".")  # strip trailing period
            found.add(ref)

    for pattern in _DOC_PATTERNS:
        for match in pattern.finditer(text):
            found.add(match.group(1).strip())  # keep full "Exhibit A"

    return sorted(found)


def remove_self_references(references: list, own_section: str) -> list:
    """Drop any reference that points back to the clause's own section number."""
    clean = own_section.rstrip(".")
    return [r for r in references if r.rstrip(".") != clean]

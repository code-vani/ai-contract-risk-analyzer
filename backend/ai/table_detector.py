import re

# Markdown table: lines with | col | col | pattern
_TABLE_PATTERN = re.compile(
    r"(\|[^\n]+\|\n(?:\|[-: ]+\|\n)?(?:\|[^\n]+\|\n)+)",
    re.MULTILINE,
)

# Keywords that flag a table as financial
_FINANCIAL_KEYWORDS = re.compile(
    r"\b(penalty|fee|milestone|price|rate|amount|cost|payment|SLA|service level|"
    r"deliverable|invoice|charge|discount|bonus|credit|refund)\b",
    re.IGNORECASE,
)


def extract_financial_tables(markdown_text: str) -> list:
    """
    Find Markdown tables in the extracted text and return them as
    FINANCIAL_TABLE clause objects — separate from normal clauses.

    The PS explicitly requires: 'Preserve table structures for complex
    terms such as penalties, fees, milestones, and service levels.'

    Returns:
        list of dicts with clause_type="financial_table"
    """
    tables = []
    for i, match in enumerate(_TABLE_PATTERN.finditer(markdown_text)):
        raw = match.group(1)
        is_financial = bool(_FINANCIAL_KEYWORDS.search(raw))
        tables.append({
            "section_number": f"TABLE-{i+1}",
            "title":          "Financial Table" if is_financial else "Data Table",
            "text":           raw.strip(),
            "clause_type":    "financial_table",
            "references_to":  [],
            "is_financial":   is_financial,
            "char_offset":    match.start(),
        })
    return tables


def strip_tables_from_text(markdown_text: str) -> tuple[str, list]:
    """
    Remove table blocks from the text before sending to Gemini
    (Gemini handles prose better without embedded table noise)
    and return (clean_text, extracted_tables).
    """
    tables = extract_financial_tables(markdown_text)
    clean  = _TABLE_PATTERN.sub("\n[TABLE EXTRACTED — SEE financial_table CLAUSES]\n", markdown_text)
    return clean, tables

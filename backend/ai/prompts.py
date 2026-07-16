from ai.ledgar_loader import LEDGAR_EXAMPLES

_VALID_TYPES = (
    "payment termination liability liability_cap confidentiality "
    "ip governing_law warranties dispute non_compete other"
)


def build_clause_extraction_prompt(contract_text: str, document_type: str) -> str:
    """
    Build the Gemini extraction prompt with LEDGAR few-shot examples.
    Called by clause_extractor for each chunk — LEDGAR examples are
    already in memory (loaded once at startup, zero added latency here).
    """

    # Build the examples section — shows Gemini what each clause type looks like
    examples_block = ""
    for clause_type, examples in LEDGAR_EXAMPLES.items():
        if examples:
            examples_block += f"\n{clause_type.upper()} examples from real contracts:\n"
            for i, ex in enumerate(examples, 1):
                examples_block += f'  {i}. "{ex}"\n'

    return (
        f"Extract all clauses from this {document_type} contract. "
        f"Return a JSON array where each element is a clause object.\n\n"
        f"CLAUSE TYPE GUIDE — real examples from 60,000 labelled contracts:\n"
        f"{examples_block}\n"
        f"Each clause object must have exactly these fields:\n"
        f"  section_number: string (e.g. \"4.1\", \"Article III\")\n"
        f"  title: string (the section heading or best short title)\n"
        f"  text: string (full clause text verbatim)\n"
        f"  document_type: \"{document_type}\"\n"
        f"  clause_type: one of [{_VALID_TYPES}]\n"
        f"  references_to: array of strings (section numbers/exhibits this clause "
        f"mentions, e.g. [\"8.2\", \"Exhibit A\"]) — empty array if none\n"
        f"  has_obligation: boolean (true if this clause creates a binding obligation)\n\n"
        f"RULES:\n"
        f"  - Include EVERY section, even boilerplate.\n"
        f"  - If clause says 'Notwithstanding Section X', add X to references_to.\n"
        f"  - Preserve exact section numbers as they appear in the document.\n"
        f"  - If no clear section number exists, use 'PREAMBLE' or 'RECITAL-N'.\n\n"
        f"CONTRACT TEXT:\n{contract_text}\n\n"
        f"Return ONLY the JSON array. No explanation."
    )

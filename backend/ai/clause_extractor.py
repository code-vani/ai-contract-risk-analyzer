import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from ai.gemini_client import call_gemini_json, call_gemini_vision_json
from ai.prompts import build_clause_extraction_prompt
from ai.reference_finder import find_references, remove_self_references
from ai.table_detector import strip_tables_from_text
from ai.cache import get_file_hash, load_cached_clauses, save_cached_clauses

# Max characters per Gemini call — stays well inside the 1M token context limit
# but keeps each call fast and focused
CHUNK_SIZE = 12_000

# Parallel Gemini calls for long contracts.
# Set to 1 on free tier (15 RPM limit). Increase to 3 with a paid billing account.
MAX_WORKERS = 1

# Regex: split text at section headings so chunks never cut mid-clause
_SECTION_HEADING = re.compile(
    r"(?m)^(?=#{1,4}\s|\d{1,2}\.\s|\bArticle\s+[IVXLC\d]+|\bSection\s+\d)",
)

# Lettered sub-clause detector: "A. Word" at the very start of a line
# Matches single uppercase letter + period + space + uppercase letter (title word)
_LETTERED_SUBCLAUSE_START = re.compile(r"(?m)^(?=[A-Z]\.\s+[A-Z])")


def extract_clauses(extraction_result: dict, document_type: str, file_path: str = None) -> list:
    """
    Main entry point. Receives Component 1 output, returns clause list.

    Args:
        extraction_result: { mode, content, ... } from smart_extractor
        document_type: "MSA" or "SOW"
        file_path: optional — enables disk cache (same file = instant result)

    Returns:
        list of clause dicts (see ClauseObject format in integration spec)
    """
    if extraction_result["mode"] == "error":
        print(f"[Extractor] Skipping — upstream error: {extraction_result['error']}")
        return []

    # Cache check — if we've seen this exact file before, skip Gemini entirely
    file_hash = None
    if file_path:
        try:
            file_hash = get_file_hash(file_path)
            cached = load_cached_clauses(file_hash, document_type)
            if cached is not None:
                print(f"[Extractor] Cache hit — {len(cached)} clauses returned instantly")
                return cached
        except Exception:
            pass

    if extraction_result["mode"] == "text":
        clauses = _extract_from_text(extraction_result["content"], document_type)
    elif extraction_result["mode"] == "image":
        clauses = _extract_from_images(extraction_result["content"], document_type)
    else:
        return []

    # Expand lettered sub-clauses (A., B., C., ...) into individual clause dicts
    clauses = _split_lettered_subclauses(clauses)

    # Persist to cache
    if file_hash and clauses:
        try:
            save_cached_clauses(file_hash, document_type, clauses)
        except Exception:
            pass

    return clauses


def _extract_from_text(markdown_text: str, document_type: str) -> list:
    # Step 1: Pull out financial tables before anything else (preserves structure)
    clean_text, tables = strip_tables_from_text(markdown_text)
    print(f"[Extractor] Found {len(tables)} table(s) — extracted separately")

    # Step 2: Smart routing — hybrid (no API) for structured docs, Gemini for the rest
    from ai.hybrid_extractor import is_structured, extract_clauses_hybrid

    if is_structured(clean_text):
        print("[Extractor] Structured document detected — using hybrid (regex + LEDGAR), 0 API calls")
        clauses = extract_clauses_hybrid(clean_text, document_type)
        if clauses:
            for t in tables:
                t["document_type"] = document_type
            clauses.extend(tables)
            print(f"[Extractor] Done — {len(clauses)} total clauses ({len(tables)} tables)")
            return clauses
        # Hybrid returned empty (model not trained yet) — fall through to Gemini
        print("[Extractor] Hybrid empty — falling back to Gemini (run ai/train_ledgar_classifier.py to fix)")
    else:
        print("[Extractor] Unstructured document — using Gemini")

    # Step 3 (Gemini path): Split at section boundaries and call API
    chunks = _split_at_sections(clean_text, CHUNK_SIZE)
    print(f"[Extractor] Contract split into {len(chunks)} chunk(s)")

    if len(chunks) == 1:
        clauses = _call_gemini_chunk(chunks[0], document_type, 1, 1)
    else:
        clauses = _process_chunks_parallel(chunks, document_type)

    # Step 4: Deduplicate + enrich references
    clauses = _deduplicate(clauses)
    clauses = _enrich_references(clauses)

    # Step 5: Append financial tables as their own clause objects
    for t in tables:
        t["document_type"] = document_type
    clauses.extend(tables)

    print(f"[Extractor] Done — {len(clauses)} total clauses ({len(tables)} tables)")
    return clauses


def _extract_from_images(images: list, document_type: str) -> list:
    """Scanned PDF fallback — one Gemini Vision call per page."""
    all_clauses = []
    for img in images:
        print(f"[Extractor] Processing page {img['page']} via Vision")
        prompt  = build_clause_extraction_prompt("(see image above)", document_type)
        result  = call_gemini_vision_json([img["base64"]], prompt)
        if isinstance(result, list):
            all_clauses.extend(result)
    return _deduplicate(_enrich_references(all_clauses))


def _process_chunks_parallel(chunks: list, document_type: str) -> list:
    """
    Send all chunks to Gemini concurrently using a thread pool.
    Results are reassembled in original order.
    """
    results = [None] * len(chunks)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {
            executor.submit(_call_gemini_chunk, chunk, document_type, i + 1, len(chunks)): i
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                print(f"[Extractor] Chunk {idx+1} failed: {e}")
                results[idx] = []

    # Flatten in order
    return [clause for chunk_result in results if chunk_result for clause in chunk_result]


def _call_gemini_chunk(chunk: str, document_type: str, chunk_num: int, total: int) -> list:
    print(f"[Extractor] Chunk {chunk_num}/{total} — {len(chunk)} chars")
    prompt  = build_clause_extraction_prompt(chunk, document_type)
    result  = call_gemini_json(prompt)

    if result is None:
        print(f"[Extractor] Chunk {chunk_num} returned no data")
        return []
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and "clauses" in result:
        return result["clauses"]
    return []


def _split_at_sections(text: str, chunk_size: int) -> list:
    """
    Split contract text at section heading boundaries.
    This ensures chunks never cut a clause in half.
    Falls back to paragraph splitting for unstructured text.
    """
    split_points = [m.start() for m in _SECTION_HEADING.finditer(text)]

    if len(split_points) < 2:
        return _split_paragraphs(text, chunk_size)

    chunks, current = [], ""
    for i, start in enumerate(split_points):
        end     = split_points[i + 1] if i + 1 < len(split_points) else len(text)
        section = text[start:end]

        if len(current) + len(section) > chunk_size and current:
            chunks.append(current.strip())
            current = section
        else:
            current += section

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if c]


def _split_paragraphs(text: str, chunk_size: int) -> list:
    """Fallback: split at double newlines (paragraphs)."""
    paras = text.split("\n\n")
    chunks, current = [], ""
    for para in paras:
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current.strip())
            current = para
        else:
            current += "\n\n" + para
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _enrich_references(clauses: list) -> list:
    """
    Scan each clause's text for cross-references with regex,
    merge with Gemini's findings, clean trailing periods,
    and remove self-references.
    """
    for clause in clauses:
        text     = clause.get("text", "")
        own_sec  = clause.get("section_number", "")
        found    = find_references(text)
        existing = [r.rstrip(".") for r in clause.get("references_to", [])]
        merged   = sorted(set(existing) | set(found))
        clause["references_to"] = remove_self_references(merged, own_sec)
    return clauses


def _split_lettered_subclauses(clauses: list) -> list:
    """
    Post-processing pass: expand any clause whose text contains lettered
    sub-clauses (A., B., C., ...) into one clause dict per sub-clause.

    Guards against false positives by requiring:
    - At least 2 sub-clauses found
    - Letters are ≥60% consecutive (A→B→C…), so random capital initials don't trigger it
    - financial_table clauses are never touched
    """
    result = []
    for clause in clauses:
        if clause.get("type") == "financial_table":
            result.append(clause)
        else:
            result.extend(_expand_lettered_clause(clause))
    return result


def _expand_lettered_clause(clause: dict) -> list:
    text = clause.get("text", "")

    # Collect (position, letter) for each sub-clause start
    splits = []
    for m in _LETTERED_SUBCLAUSE_START.finditer(text):
        snippet = text[m.start():m.start() + 8]
        lm = re.match(r"^([A-Z])\.\s+[A-Z]", snippet)
        if lm:
            splits.append((m.start(), lm.group(1)))

    if len(splits) < 2:
        return [clause]

    # Require letters to be mostly consecutive (A, B, C …)
    letters = [s[1] for s in splits]
    consecutive = sum(
        1 for i in range(1, len(letters))
        if ord(letters[i]) == ord(letters[i - 1]) + 1
    )
    if consecutive / max(len(letters) - 1, 1) < 0.6:
        return [clause]

    parent_section = clause.get("section_number", "")
    sub_clauses = []

    for i, (pos, letter) in enumerate(splits):
        end = splits[i + 1][0] if i + 1 < len(splits) else len(text)
        sub_text = text[pos:end].strip()

        # Title = text between "A. " and the next period
        title_m = re.match(r"^[A-Z]\.\s+([^.]+)\.", sub_text)
        title = title_m.group(1).strip() if title_m else sub_text[:60].strip()

        sub = dict(clause)
        sub["section_number"] = f"{parent_section}.{letter}" if parent_section else letter
        sub["title"] = title
        sub["text"] = sub_text
        sub_clauses.append(sub)

    print(f"[Extractor] Sub-clause split '{parent_section}' → {[s['section_number'] for s in sub_clauses]}")
    return sub_clauses


def _deduplicate(clauses: list) -> list:
    """Remove duplicate section numbers — keeps first occurrence."""
    seen, unique = set(), []
    for c in clauses:
        key = c.get("section_number", "")
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique

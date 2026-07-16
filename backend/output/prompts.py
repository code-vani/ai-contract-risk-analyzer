"""Prompt templates for Component 5 (redline generation).

Kept as module-level constants so they are easy to tune without touching logic.
"""

REDLINE_PROMPT = """You are a senior contracts attorney producing a Track-Changes style redline.

RULES — follow exactly:
1. MINIMUM CHANGE: Alter only the words necessary to fix the risk. Keep every other word identical.
2. COMPLETE CLAUSE: suggested_text must be the entire rewritten clause, not a fragment or summary.
3. NO ADDED PROSE: Do not insert explanatory text, citations, or commentary into the clause.
4. STRATEGY:
   - CONTRADICTION → change the conflicting value/term to match the governing document (MSA typically wins).
   - OVERRIDE → remove or narrow "notwithstanding"/"supersedes" language so the clause no longer blanket-overrides.
   - Other → apply the minimal change described in SUGGESTED CHANGE.

ORIGINAL TEXT: {original_text}
RISK DESCRIPTION: {risk_description}
SUGGESTED CHANGE: {suggested_change}

Return ONLY a single JSON object — no markdown, no code fences, no prose:
  "suggested_text": full rewritten clause (string)
  "change_summary": one sentence describing the edit, e.g. "Changed '45 days' to '30 days' to match MSA § 4.1" (string)
  "words_removed":  exact phrase(s) deleted from the original (list of strings)
  "words_added":    exact phrase(s) inserted in their place (list of strings)
  "change_type":    "ADD" | "REMOVE" | "MODIFY"

Example:
{{"suggested_text": "Payment shall be due within thirty (30) days of invoice.", "change_summary": "Changed '45 days' to '30 days' to align with MSA payment terms.", "words_removed": ["forty-five (45)"], "words_added": ["thirty (30)"], "change_type": "MODIFY"}}
"""


BATCH_REDLINE_PROMPT = """You are a senior contracts attorney producing Track-Changes style redlines.
You receive a JSON array of contract clause issues. For each issue, produce a minimal word-level edit that resolves the stated risk.

FIXED RULES — apply to every issue without exception:
1. MINIMUM CHANGE: Alter only the words necessary to fix the risk. Keep every other word identical to the original.
   Do not restructure sentences, reorder clauses, or change legal terminology unless it is itself the problem.
2. COMPLETE CLAUSE: suggested_text must be the entire rewritten clause — not a fragment, not a paraphrase.
3. NO ADDED PROSE: Do not insert explanatory text, cross-references, or commentary into the clause text.
4. STRATEGY BY RISK TYPE:
   - "CONTRADICTION" → change the conflicting value/term in the SOW clause to match the MSA.
     Use which_wins to know which document governs. Example: "45 days" → "30 days".
   - "OVERRIDE" → two sub-cases:
     a. If the override is a single phrase ("Notwithstanding Section X") prepended to an otherwise valid clause:
        delete only that phrase and adjust the opening so the clause is still grammatically complete.
     b. If the ENTIRE clause's legal purpose conflicts with the MSA (e.g. Vendor-IP retention clause when MSA
        says Client owns everything) — rewrite the ownership/obligation sentence to reflect which_wins.
        Example: "shall remain the sole and exclusive intellectual property of the Vendor for six (6) months...
        Vendor grants Client a limited license..." → "shall be owned by Client as a work made for hire upon
        delivery, consistent with the intellectual property provisions of the MSA."
        Do NOT make trivial word changes (e.g. "remain" → "be") that leave the legal meaning unchanged.
   - Other types → apply the minimal change described in suggested_change.
5. words_removed = exact token(s) deleted from the original (must be verbatim substrings of original_text).
6. words_added   = exact token(s) inserted in place of the removed tokens.

ISSUES (JSON):
{issues_json}

Return ONLY a JSON array — no markdown, no code fences, no prose before or after.
One object per issue (in any order), each with exactly these keys:
  "risk_id"        : string — copy from the issue
  "suggested_text" : string — full rewritten clause
  "change_summary" : string — one sentence, e.g. "Changed '45 days' to '30 days' to align with MSA § 4.1"
  "words_removed"  : list of strings
  "words_added"    : list of strings
  "change_type"    : "ADD" | "REMOVE" | "MODIFY"

EXAMPLES (for calibration — do not include in output):

Example 1 — CONTRADICTION (payment terms):
  Input issue:  {{"risk_id":"X","original_text":"Payment shall be due within forty-five (45) days of invoice.","risk_description":"SOW specifies 45 days; MSA requires 30 days.","risk_type":"CONTRADICTION","which_wins":"MSA governs; 30-day term applies.","suggested_change":"Change to 30 days to match MSA"}}
  Correct output: {{"risk_id":"X","suggested_text":"Payment shall be due within thirty (30) days of invoice.","change_summary":"Changed '45 days' to '30 days' to match MSA payment terms.","words_removed":["forty-five (45)"],"words_added":["thirty (30)"],"change_type":"MODIFY"}}

Example 2a — OVERRIDE (simple prepended phrase, rest of clause is fine):
  Input issue:  {{"risk_id":"Y","original_text":"Notwithstanding MSA Section 5, invoices shall be paid within 60 days.","risk_description":"Override of MSA 30-day payment terms.","risk_type":"OVERRIDE","which_wins":"MSA 30-day term governs.","suggested_change":"Remove notwithstanding phrase; align to MSA payment terms."}}
  Correct output: {{"risk_id":"Y","suggested_text":"Invoices shall be paid within thirty (30) days, consistent with MSA Section 5.","change_summary":"Removed 'Notwithstanding MSA Section 5' override and aligned payment term to MSA 30-day standard.","words_removed":["Notwithstanding MSA Section 5, invoices shall be paid within 60 days."],"words_added":["Invoices shall be paid within thirty (30) days, consistent with MSA Section 5."],"change_type":"MODIFY"}}

Example 2b — OVERRIDE (entire clause conflicts — IP ownership):
  Input issue:  {{"risk_id":"Z","original_text":"All software and artifacts developed under this SOW shall remain the sole and exclusive intellectual property of the Vendor for six (6) months following delivery. During this retention period, Vendor grants Client a limited, non-exclusive license to use the deliverables for internal purposes.","risk_description":"SOW grants Vendor IP retention and only a limited license to Client, conflicting with MSA work-for-hire provisions where Client owns all deliverables.","risk_type":"OVERRIDE","which_wins":"MSA work-for-hire provisions govern; Client owns all deliverables upon delivery.","suggested_change":"Remove Vendor IP retention; apply MSA work-for-hire ownership."}}
  Correct output: {{"risk_id":"Z","suggested_text":"All software and artifacts developed under this SOW shall be owned by Client as works made for hire upon delivery, consistent with the intellectual property provisions of the MSA.","change_summary":"Replaced Vendor IP retention structure with MSA work-for-hire ownership; Client owns all deliverables upon delivery.","words_removed":["remain the sole and exclusive intellectual property of the Vendor for six (6) months following delivery. During this retention period, Vendor grants Client a limited, non-exclusive license to use the deliverables for internal purposes."],"words_added":["be owned by Client as works made for hire upon delivery, consistent with the intellectual property provisions of the MSA."],"change_type":"MODIFY"}}
"""

"""
contradiction_detector.py — Task 1 & Task 4

Asks Gemini whether two clauses (one MSA, one SOW, same topic) contradict
each other. Built to fail *safely*: if anything goes wrong (no API key,
network error, garbage JSON back from the model), we never crash the
pipeline — we return a clearly-marked "could not determine" result instead
of silently guessing.

Uses the same google-genai SDK and GEMINI_API_KEY as Component 2, so no
extra API key or package is needed — just the one key already in backend/.env.
"""

import json
import os
import re
import time
import logging

# Load .env as soon as this module is imported, regardless of which script
# is the entry point (test.py, risk_pipeline.py, a future FastAPI app,
# etc). Without this, GROQ_API_KEY only exists in os.environ if whatever
# script you happened to run called load_dotenv() itself first — which is
# an easy thing to forget and fails *silently* (falls through to the
# "AI service unavailable" branch below, no crash, no obvious error).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — fine if GEMINI_API_KEY is set another way (export, CI secrets, etc)

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {
    "is_contradiction": False,
    "severity": "LOW",
    "description": "Model did not return this field.",
    "which_wins": "Unknown — review manually.",
    "confidence": 0.0,
}

VALID_SEVERITIES = {"HIGH", "MEDIUM", "LOW"}

MAX_CLAUSE_CHARS = 4000  # guard against megatables blowing up the prompt

CONTRADICTION_PROMPT_TEMPLATE = """You are a contract analysis assistant. You will be given two pieces of contract text covering the same topic.

Decide whether they contradict each other. Two kinds of conflict both count as a contradiction:

1. DIRECT CONFLICT — a party literally could not comply with both at once, or one materially changes the obligation set by the other (e.g. one requires payment in 30 days, the other in 45).

2. IMPLIED FALSEHOOD — Text B makes a claim about an obligation, right, permission, or scope that Text A's actual wording does not support, such that Text A being true makes Text B false. This includes cases where Text A is exhaustive or silent on a point that Text B asserts as mandatory or guaranteed — silence or a broader/narrower scope in Text A can still contradict a specific claim in Text B.

Respond with ONLY a valid JSON object. No markdown, no code fences, no extra commentary before or after. Use exactly this shape:
{{
  "is_contradiction": true or false,
  "severity": "HIGH" or "MEDIUM" or "LOW",
  "description": "one or two sentence explanation of the conflict, or why there is none",
  "which_wins": "explain which clause would likely take precedence and why, or 'N/A' if no contradiction",
  "confidence": a number between 0.0 and 1.0
}}

Two worked examples (for calibration only — not part of the comparison below):

Example 1 — IS a contradiction (implied falsehood):
  Text A: "Confidential Information includes all information disclosed in any form, whether written, oral, or otherwise, with no marking or designation required."
  Text B: "All Confidential Information shall be expressly identified by the Disclosing Party."
  → is_contradiction: true — Text A explicitly makes unmarked disclosures qualify as confidential, which conflicts with Text B's claim that marking is required.

Example 2 — NOT a contradiction (Text B is supported, not contradicted):
  Text A: "Confidential Information may be disclosed to Recipient's employees on a need-to-know basis."
  Text B: "Receiving Party may share Confidential Information with some of its employees."
  → is_contradiction: false — Text B follows directly from Text A.

Now compare the actual texts:

TEXT A ({doc_type_a} {section_a}):
{text_a}

TEXT B ({doc_type_b} {section_b}):
{text_b}
"""


_MAX_ROUNDS = 4
_MAX_WAIT_SECONDS = 90

try:
    from ai.key_pool import pool as _pool
except ImportError:
    # Flat-import path when running this file directly from analysis/
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
    from ai.key_pool import pool as _pool

try:
    from google.genai import types as _types
    _GENAI_CFG = _types.GenerateContentConfig(
        response_mime_type="application/json",
        max_output_tokens=800,
    )
except ImportError:
    _GENAI_CFG = None


def _parse_rate_limit_wait(msg: str, backoff_round: int) -> float:
    """Extract the retry-after delay from a 429 error, with exponential backoff fallback."""
    m = re.search(r"retry[_ ](?:in|after)\s+([0-9.]+)", msg, re.IGNORECASE)
    suggested = float(m.group(1)) if m else (5.0 * (2 ** backoff_round))
    return min(suggested + 1.0, _MAX_WAIT_SECONDS)


def _call_gemini_raw(prompt: str) -> str | None:
    """
    Calls Gemini with JSON mode enforced. Returns the raw JSON string, or
    None if the call could not be made (missing key, network error, etc).
    Never raises — callers should treat None as "no answer available".

    Uses the shared GeminiKeyPool — rotates across all configured API keys
    so rate-limit pressure is distributed evenly with the rest of the pipeline.
    On 429: switches to the next key immediately; only sleeps after all keys
    have been tried in a single round.
    """
    if not _pool or _GENAI_CFG is None:
        logger.warning("No Gemini keys configured — skipping contradiction check.")
        return None

    pool_size = len(_pool)
    max_retries = pool_size * _MAX_ROUNDS

    for attempt in range(max_retries):
        client = _pool.next()
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config=_GENAI_CFG,
            )
            return response.text
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if re.search(r"429|ResourceExhausted|RESOURCE_EXHAUSTED|quota|rate.?limit", msg, re.IGNORECASE):
                pos = attempt % pool_size
                if pos < pool_size - 1:
                    # More keys to try this round — switch immediately
                    logger.warning(f"[contradiction] Rate-limited — switching to next key ({pos + 1}/{pool_size})")
                    continue
                elif attempt < max_retries - 1:
                    # End of a round — wait before next round
                    backoff_round = attempt // pool_size
                    wait = _parse_rate_limit_wait(msg, backoff_round)
                    logger.warning(f"[contradiction] All keys rate-limited — waiting {wait:.0f}s (round {backoff_round + 1}/{_MAX_ROUNDS})")
                    time.sleep(wait)
                else:
                    logger.error(f"[contradiction] Rate-limit retries exhausted: {e}")
                    return None
            else:
                logger.error(f"AI call failed: {e}")
                return None
    return None



def _extract_json_block(raw_text: str) -> str:
    """
    Gemini sometimes wraps JSON in ```json ... ``` fences, or adds a
    sentence before/after despite instructions. Strip fences first, then
    fall back to regex-extracting the first {...} block.
    """
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)

    return text  # let json.loads fail naturally and be caught by caller


def _validate_and_fill(parsed: dict) -> dict:
    """Fill any missing/invalid fields with safe defaults instead of KeyError-ing downstream."""
    result = dict(REQUIRED_FIELDS)
    result.update({k: v for k, v in parsed.items() if k in REQUIRED_FIELDS})

    if not isinstance(result.get("is_contradiction"), bool):
        result["is_contradiction"] = bool(result.get("is_contradiction", False))

    if result.get("severity") not in VALID_SEVERITIES:
        result["severity"] = "LOW"

    try:
        conf = float(result.get("confidence", 0.0))
        result["confidence"] = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        result["confidence"] = 0.0

    if not isinstance(result.get("description"), str) or not result["description"].strip():
        result["description"] = REQUIRED_FIELDS["description"]

    if not isinstance(result.get("which_wins"), str) or not result["which_wins"].strip():
        result["which_wins"] = REQUIRED_FIELDS["which_wins"]

    return result


def detect_contradiction(clause_a: dict, clause_b: dict, _call_fn=_call_gemini_raw) -> dict:
    """
    Compare two clause dicts (each needs at least 'section_number' and 'text').
    Returns a dict matching REQUIRED_FIELDS' shape — never raises.

    `_call_fn` is injectable purely for testing (see test_detector.py) so
    tests don't need a real API key or network access.
    """
    text_a = (clause_a or {}).get("text", "") or ""
    text_b = (clause_b or {}).get("text", "") or ""
    section_a = (clause_a or {}).get("section_number", "?")
    section_b = (clause_b or {}).get("section_number", "?")
    doc_type_a = (clause_a or {}).get("document_type") or "Document"
    doc_type_b = (clause_b or {}).get("document_type") or "Document"

    # Edge case: empty clause text — nothing to compare.
    if not text_a.strip() or not text_b.strip():
        return _validate_and_fill({
            "is_contradiction": False,
            "severity": "LOW",
            "description": "One or both clauses had no extractable text — cannot compare.",
            "which_wins": "N/A",
            "confidence": 0.0,
        })

    # Edge case: comparing a clause against itself (bad pairing upstream).
    if section_a == section_b and text_a.strip() == text_b.strip():
        return _validate_and_fill({
            "is_contradiction": False,
            "severity": "LOW",
            "description": "Clause A and Clause B are identical — likely a duplicate pairing, not a real comparison.",
            "which_wins": "N/A",
            "confidence": 1.0,
        })

    # Edge case: guard against extremely long clause text (e.g. an entire
    # mis-parsed table dumped into one clause) blowing the prompt budget.
    text_a_trunc = text_a[:MAX_CLAUSE_CHARS]
    text_b_trunc = text_b[:MAX_CLAUSE_CHARS]

    prompt = CONTRADICTION_PROMPT_TEMPLATE.format(
        section_a=section_a, section_b=section_b, text_a=text_a_trunc, text_b=text_b_trunc,
        doc_type_a=doc_type_a, doc_type_b=doc_type_b,
    )

    raw = _call_fn(prompt)
    if raw is None:
        return _validate_and_fill({
            "is_contradiction": False,
            "severity": "LOW",
            "description": "AI service unavailable — contradiction check could not run for this pair.",
            "which_wins": "Unknown — requires manual review.",
            "confidence": 0.0,
        })

    json_block = _extract_json_block(raw)

    try:
        parsed = json.loads(json_block)
        if not isinstance(parsed, dict):
            raise ValueError("Response JSON was not an object")
        return _validate_and_fill(parsed)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"First parse failed ({e}), retrying once with a stricter prompt.")

    # Task 3 (retry once) — ask again, more forcefully, no re-sending both
    # full clause texts to save tokens; just demand valid JSON of what we got back.
    retry_prompt = (
        "The following was supposed to be a single valid JSON object but is not. "
        "Return ONLY the corrected valid JSON object, nothing else:\n\n" + raw
    )
    raw_retry = _call_fn(retry_prompt)
    if raw_retry:
        try:
            parsed_retry = json.loads(_extract_json_block(raw_retry))
            if isinstance(parsed_retry, dict):
                return _validate_and_fill(parsed_retry)
        except (json.JSONDecodeError, ValueError):
            pass

    return _validate_and_fill({
        "is_contradiction": False,
        "severity": "LOW",
        "description": "AI response could not be parsed as valid JSON after retry — flagged for manual review.",
        "which_wins": "Unknown — requires manual review.",
        "confidence": 0.0,
    })


def detect_all_contradictions(pairs: list[dict], delay_seconds: float = 0.5, _call_fn=_call_gemini_raw) -> list[dict]:
    """
    Task 4 — Batch processing.

    pairs: list of { "clause_a": {...}, "clause_b": {...} }
    Processes one at a time with a small delay to avoid rate limits.
    A single pair's failure never aborts the whole batch — it's recorded
    as a low-confidence non-contradiction with a note in the description.

    Returns a list of risk-shaped dicts (only ones where is_contradiction
    is True are returned as CONTRADICTION risks — see Task 5 note below).
    """
    if not pairs:
        return []

    results = []
    for i, pair in enumerate(pairs):
        clause_a = pair.get("clause_a")
        clause_b = pair.get("clause_b")

        if not clause_a or not clause_b:
            logger.warning(f"Skipping malformed pair at index {i}: missing clause_a/clause_b.")
            continue

        try:
            outcome = detect_contradiction(clause_a, clause_b, _call_fn=_call_fn)
        except Exception as e:  # noqa: BLE001 — one bad pair must not kill the batch
            logger.error(f"Unexpected error comparing pair {i}: {e}")
            outcome = _validate_and_fill({
                "is_contradiction": False,
                "description": f"Unexpected error during comparison: {e}",
            })

        if outcome["is_contradiction"]:
            results.append({
                "type": "CONTRADICTION",
                "severity": outcome["severity"],
                "clause_a": {
                    "section": clause_a.get("section_number", "?"),
                    "document_type": clause_a.get("document_type", ""),
                    "text": clause_a.get("text", ""),
                },
                "clause_b": {
                    "section": clause_b.get("section_number", "?"),
                    "document_type": clause_b.get("document_type", ""),
                    "text": clause_b.get("text", ""),
                },
                "description": outcome["description"],
                "which_wins": outcome["which_wins"],
                "confidence": outcome["confidence"],
            })

        # Don't sleep after the last item — no point.
        if i < len(pairs) - 1:
            time.sleep(delay_seconds)

    return results


if __name__ == "__main__":
    # Quick manual smoke test (no API key needed — uses a fake call_fn).
    def fake_gemini(prompt: str) -> str:
        return json.dumps({
            "is_contradiction": True,
            "severity": "HIGH",
            "description": "SOW allows 45 days; MSA requires 30 days.",
            "which_wins": "MSA governs unless SOW explicitly overrides via Notwithstanding language.",
            "confidence": 0.95,
        })

    clause_a = {"section_number": "MSA-4.1", "text": "Payment shall be due within thirty (30) days."}
    clause_b = {"section_number": "SOW-2.3", "text": "Payment shall be due within forty-five (45) days."}

    result = detect_contradiction(clause_a, clause_b, _call_fn=fake_gemini)
    print(json.dumps(result, indent=2))
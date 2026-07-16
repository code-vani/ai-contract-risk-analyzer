"""Gemini text client used by Component 5 (redlines).

Uses the shared GeminiKeyPool from ai.key_pool so redline calls participate in
the same round-robin rotation as the rest of the pipeline — maximising the
combined RPM across all configured API keys.
"""

import json
import re
import time

from google.genai import types as _genai_types

from ai.key_pool import pool as _pool

_MAX_ROUNDS = 4
_MAX_RETRY_WAIT_SECONDS = 90.0
_REDLINE_MODEL = "gemini-3.1-flash-lite"


def is_mock() -> bool:
    """True when no real Gemini client is available (mock responses in use)."""
    return not bool(_pool)


def call_gemini(prompt: str, max_tokens: int = 2000) -> str | None:
    """Send a prompt to Gemini, retrying on rate-limit errors.

    Each round tries every key before sleeping — so with 3 keys, 3 consecutive
    429s trigger one wait, not one wait after the very first 429.
    """
    if not _pool:
        print("[redline] No API keys — using mock response")
        return _mock_response(prompt)

    pool_size = len(_pool)
    max_retries = pool_size * _MAX_ROUNDS
    cfg = _genai_types.GenerateContentConfig(max_output_tokens=max_tokens)

    for attempt in range(max_retries):
        client = _pool.next()
        try:
            resp = client.models.generate_content(
                model=_REDLINE_MODEL,
                contents=prompt,
                config=cfg,
            )
            return resp.text
        except Exception as exc:
            msg = str(exc)
            is_rate_limit = re.search(
                r"429|ResourceExhausted|RESOURCE_EXHAUSTED|quota|rate.?limit",
                msg, re.IGNORECASE
            )
            if is_rate_limit:
                pos = attempt % pool_size
                if pos < pool_size - 1:
                    print(f"[redline] Rate limited — switching to next key ({pos + 1}/{pool_size})")
                    continue
                elif attempt < max_retries - 1:
                    backoff_round = attempt // pool_size
                    m = re.search(r"retry[_ ](?:in|after)\s+([0-9.]+)", msg, re.IGNORECASE)
                    suggested = float(m.group(1)) if m else (5.0 * (2 ** backoff_round))
                    delay = min(suggested + 1.0, _MAX_RETRY_WAIT_SECONDS)
                    print(f"[redline] All keys rate-limited, waiting {delay:.0f}s (round {backoff_round + 1}/{_MAX_ROUNDS})…")
                    time.sleep(delay)
                else:
                    print("[redline] All retries exhausted — using fallback.")
                    return None
            else:
                print(f"[redline] Gemini call failed (non-retryable): {exc}")
                return None

    return None


def _mock_response(prompt: str) -> str:
    """Deterministic stand-in when no API key is configured."""
    if "ISSUES (JSON):" in prompt:
        return _mock_batch(prompt)
    original = _extract_field(prompt, "ORIGINAL TEXT")
    suggested_change = _extract_field(prompt, "SUGGESTED CHANGE")
    return json.dumps(_mock_one(original, suggested_change))


def _mock_one(original: str, suggested_change: str) -> dict:
    suggested_text = original
    words_removed: list[str] = []
    words_added: list[str] = []

    substitutions = [
        (r"forty-five \(45\)", "thirty (30)"),
        (r"seven \(7\)", "thirty (30)"),
    ]
    for pattern, replacement in substitutions:
        if re.search(pattern, suggested_text):
            words_removed.append(re.search(pattern, suggested_text).group(0))
            words_added.append(replacement)
            suggested_text = re.sub(pattern, replacement, suggested_text)

    if not words_removed and original:
        note = " (revised to align with the governing MSA clause)"
        suggested_text = original + note
        words_added.append(note.strip())

    return {
        "suggested_text": suggested_text,
        "change_summary": suggested_change or "Revise clause to align with the governing MSA.",
        "words_removed": words_removed,
        "words_added": words_added,
        "change_type": "MODIFY" if words_removed else "ADD",
    }


def _mock_batch(prompt: str) -> str:
    m = re.search(r"ISSUES \(JSON\):\s*(\[.*\])\s*Return ONLY", prompt, re.DOTALL)
    if not m:
        return "[]"
    try:
        issues = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return "[]"

    out = []
    for issue in issues:
        redline = _mock_one(issue.get("original_text", ""), issue.get("suggested_change", ""))
        redline["risk_id"] = issue.get("risk_id", "")
        out.append(redline)
    return json.dumps(out)


def _extract_field(prompt: str, label: str) -> str:
    m = re.search(rf"{re.escape(label)}:\s*(.+)", prompt)
    return m.group(1).strip() if m else ""

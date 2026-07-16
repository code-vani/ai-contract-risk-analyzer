"""Component 5, Tasks 1 & 2 — AI redline generation.

For each risk, ask Gemini to produce a precise word-level fix (like Track
Changes). HIGH/MEDIUM risks get a full redline; LOW risks get a lightweight note.
Every failure mode degrades to a safe fallback so the pipeline never crashes.
"""

import json
import re

from ai.redline_client import call_gemini, is_mock
from output.prompts import BATCH_REDLINE_PROMPT, REDLINE_PROMPT

_REQUIRED_KEYS = ("suggested_text", "change_summary", "words_removed", "words_added", "change_type")


def _strip_code_fences(text: str) -> str:
    """Remove accidental ```json ... ``` fences the model may add."""
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return fence.group(1).strip() if fence else text


def _parse_redline(raw: str, original_text: str) -> dict:
    """Parse and normalise a redline JSON response, filling any missing keys."""
    data = json.loads(_strip_code_fences(raw))
    if not isinstance(data, dict):
        raise ValueError("redline response was not a JSON object")
    return {
        "suggested_text": str(data.get("suggested_text") or original_text),
        "change_summary": str(data.get("change_summary") or "Review recommended"),
        "words_removed": list(data.get("words_removed") or []),
        "words_added": list(data.get("words_added") or []),
        "change_type": str(data.get("change_type") or "MODIFY"),
    }


def _fallback(original_text: str) -> dict:
    """Safe redline used when the model call or parse fails."""
    return {
        "suggested_text": original_text,
        "change_summary": "Manual review recommended",
        "words_removed": [],
        "words_added": [],
        "change_type": "MODIFY",
    }


def generate_redline(original_text: str, risk_description: str, suggested_change: str) -> dict:
    """Generate a single word-level redline for one clause.

    Returns a dict with keys: suggested_text, change_summary, words_removed,
    words_added, change_type. Never raises — degrades to a safe fallback.
    """
    prompt = REDLINE_PROMPT.format(
        original_text=original_text,
        risk_description=risk_description,
        suggested_change=suggested_change,
    )
    raw = call_gemini(prompt)
    if not raw:
        return _fallback(original_text)
    try:
        return _parse_redline(raw, original_text)
    except (json.JSONDecodeError, ValueError):
        return _fallback(original_text)


def _batch_generate(risks: list[dict]) -> dict[str, dict]:
    """Generate redlines for many risks in a SINGLE Gemini call.

    If the batch call fails (e.g. prompt too large), falls back to individual
    per-risk calls so at least some suggestions are generated.
    """
    issues = [
        {
            "risk_id": r.get("risk_id") or f"IDX-{i}",
            "original_text": r.get("original_text", "") or "",
            "risk_description": r.get("description", ""),
            "risk_type": r.get("type", ""),
            "which_wins": r.get("which_wins", ""),
            "suggested_change": r.get("change_summary", "") or "Align this clause with the MSA.",
        }
        for i, r in enumerate(risks)
    ]
    originals = {iss["risk_id"]: iss["original_text"] for iss in issues}

    # --- Try batch first (1 API call for all risks) ---
    print(f"[redline] _batch_generate: {len(issues)} risk(s), mock={is_mock()}")
    prompt = BATCH_REDLINE_PROMPT.format(issues_json=json.dumps(issues, ensure_ascii=False))
    raw = call_gemini(prompt, max_tokens=4000)
    print(f"[redline] batch call returned {'text (' + str(len(raw)) + ' chars)' if raw else 'None'}")
    if raw:
        try:
            data = json.loads(_strip_code_fences(raw))
            if isinstance(data, list):
                result: dict[str, dict] = {}
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    rid = str(item.get("risk_id", ""))
                    if rid in originals:
                        result[rid] = _normalise_fields(item, originals[rid])
                if result:
                    return result
        except (json.JSONDecodeError, ValueError):
            pass

    # --- Batch failed — try each risk individually ---
    print("[redline] Batch call failed; falling back to per-risk individual calls.")
    result = {}
    for iss in issues:
        print(f"[redline] Generating redline for {iss['risk_id']}…")
        single = generate_redline(
            iss["original_text"],
            iss["risk_description"],
            iss["suggested_change"],
        )
        if single and single.get("suggested_text", "") != iss["original_text"]:
            result[iss["risk_id"]] = single
    return result


def _normalise_fields(data: dict, original_text: str) -> dict:
    """Coerce a redline dict to the required keys, filling any that are missing."""
    return {
        "suggested_text": str(data.get("suggested_text") or original_text),
        "change_summary": str(data.get("change_summary") or "Review recommended"),
        "words_removed": list(data.get("words_removed") or []),
        "words_added": list(data.get("words_added") or []),
        "change_type": str(data.get("change_type") or "MODIFY"),
    }


def generate_redlines(risks: list[dict]) -> list[dict]:
    """Attach a redline to each risk and return the enriched list.

    HIGH/MEDIUM severity -> full redline (generated for all such risks in ONE
    batched Gemini call) written back onto the agreed RiskObject fields
    (suggested_text, change_summary) plus a `redline` sub-dict carrying
    words_removed/words_added/change_type.
    LOW severity -> a lightweight "Review recommended" note, no API call.
    """
    # Assign stable ids so batch results can be mapped back reliably.
    for i, risk in enumerate(risks):
        risk.setdefault("risk_id", f"IDX-{i}")

    # FINANCIAL_CLAUSE risks flag specific figures for human review — AI cannot
    # know what the correct dollar/percentage value should be, so we skip the
    # AI redline and instead leave a targeted human-review note.
    to_redline = [
        r for r in risks
        if str(r.get("severity", "")).upper() in ("HIGH", "MEDIUM")
        and r.get("type") != "FINANCIAL_CLAUSE"
    ]
    print(f"[redline] generate_redlines: {len(risks)} total risk(s), {len(to_redline)} eligible for AI redlining")
    redline_map = _batch_generate(to_redline) if to_redline else {}

    enriched: list[dict] = []
    for risk in risks:
        risk = dict(risk)  # avoid mutating caller's objects
        severity = str(risk.get("severity", "")).upper()
        original_text = risk.get("original_text", "") or ""

        # Frontend expects `id`; C4 may only set `risk_id`.
        risk["id"] = risk.get("risk_id", "")

        if risk.get("type") == "FINANCIAL_CLAUSE":
            # Financial figures (dollar amounts, percentages, SLA thresholds) require
            # human expertise — AI cannot determine the correct value. Skip redline.
            risk["suggested_text"] = ""
            risk["change_summary"] = (
                "Verify financial figures match MSA terms. "
                "AI redline skipped — exact amounts require manual review."
            )
            risk["redline"] = None
        elif severity in ("HIGH", "MEDIUM"):
            redline = redline_map.get(risk["risk_id"]) or _fallback(original_text)
            risk["suggested_text"] = redline["suggested_text"]
            risk["change_summary"] = redline["change_summary"]
            risk["redline"] = {
                "words_removed": redline["words_removed"],
                "words_added": redline["words_added"],
                "change_type": redline["change_type"],
            }
        else:
            risk["suggested_text"] = risk.get("suggested_text", "") or ""
            risk["change_summary"] = "Review recommended"
            risk["redline"] = None

        enriched.append(risk)

    return enriched

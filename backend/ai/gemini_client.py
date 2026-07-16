import json
import re
import time
from google.genai import types

from ai.key_pool import pool as _pool

# gemini-3.1-flash-lite: fast, available, returns clean JSON mode responses
EXTRACTION_MODEL = "gemini-3.1-flash-lite"

_JSON_CONFIG = types.GenerateContentConfig(
    response_mime_type="application/json",
    max_output_tokens=8192,
)

_MAX_ROUNDS = 4    # how many full key-rotation rounds to attempt before giving up
_MAX_WAIT_SECONDS = 90


def _parse_retry_delay(error_msg: str, backoff_round: int = 0) -> float:
    """Extract retry delay from Gemini's 429 message, with exponential backoff fallback."""
    m = re.search(r"retry[_ ](?:in|after)\s+([0-9.]+)", error_msg, re.IGNORECASE)
    suggested = float(m.group(1)) if m else (5.0 * (2 ** backoff_round))
    return min(suggested + 1.0, _MAX_WAIT_SECONDS)


def call_gemini_json(prompt: str) -> list | dict | None:
    """
    Call Gemini with JSON mode enforced.
    Each round tries every key in the pool before sleeping.
    """
    if not _pool:
        return None

    pool_size = len(_pool)
    max_retries = pool_size * _MAX_ROUNDS

    for attempt in range(max_retries):
        client = _pool.next()

        try:
            response = client.models.generate_content(
                model=EXTRACTION_MODEL,
                contents=prompt,
                config=_JSON_CONFIG,
            )
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            print(f"[Gemini] JSON decode failed: {e}")
            return None
        except Exception as e:
            msg = str(e)
            is_rate_limit = re.search(
                r"429|ResourceExhausted|RESOURCE_EXHAUSTED|quota|rate.?limit",
                msg, re.IGNORECASE
            )
            if is_rate_limit:
                pos = attempt % pool_size
                if pos < pool_size - 1:
                    # More keys to try this round — switch immediately
                    print(f"[Gemini] Rate limited — switching to next key ({pos + 1}/{pool_size})")
                    continue
                elif attempt < max_retries - 1:
                    # End of a round — wait, then start next round
                    backoff_round = attempt // pool_size
                    wait = _parse_retry_delay(msg, backoff_round)
                    print(f"[Gemini] All keys rate-limited — waiting {wait:.0f}s (round {backoff_round + 1}/{_MAX_ROUNDS})")
                    time.sleep(wait)
                else:
                    print(f"[Gemini] Rate limit retries exhausted: {e}")
                    return None
            elif "503" in msg and attempt < max_retries - 1:
                print(f"[Gemini] Service unavailable — retrying in 10s")
                time.sleep(10)
            else:
                print(f"[Gemini] API error: {e}")
                return None

    return None


def call_gemini_vision_json(base64_images: list, prompt: str) -> list | dict | None:
    """Call Gemini Vision with JSON mode for scanned PDF pages."""
    import base64 as b64lib
    client = _pool.next()
    if client is None:
        return None
    try:
        parts = [
            types.Part.from_bytes(data=b64lib.b64decode(b64), mime_type="image/jpeg")
            for b64 in base64_images
        ]
        parts.append(types.Part.from_text(text=prompt))
        response = client.models.generate_content(
            model=EXTRACTION_MODEL,
            contents=parts,
            config=_JSON_CONFIG,
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[Gemini Vision] API error: {e}")
        return None

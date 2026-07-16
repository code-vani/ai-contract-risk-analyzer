"""Shared Gemini API key pool — round-robin across all configured keys.

All three pipeline components (gemini_client, redline_client, contradiction_detector)
import the same `pool` singleton so calls are distributed globally.

With N free-tier keys (15 RPM each) the effective limit is N × 15 RPM.
When a key returns 429, the caller should immediately try pool.next() again
(the next key) before sleeping — halving wait time when one key still has quota.
"""

import itertools
import threading

import config

try:
    from google import genai as _genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


class GeminiKeyPool:
    """Thread-safe round-robin pool of genai.Client instances."""

    def __init__(self, keys: list[str]):
        valid = [k.strip() for k in keys if k and k.strip()]
        if not _GENAI_AVAILABLE or not valid:
            self._clients: list = []
            self._size = 0
            return
        self._clients = [_genai.Client(api_key=k) for k in valid]
        self._size = len(self._clients)
        self._cycle = itertools.cycle(self._clients)
        self._lock = threading.Lock()

    # ── Public API ──────────────────────────────────────────────────────────

    def next(self):
        """Return the next client in round-robin order, or None if no keys."""
        if not self._clients:
            return None
        with self._lock:
            return next(self._cycle)

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0


# ── Module-level singleton ─────────────────────────────────────────────────
# Collect all non-empty keys. Duplicates are fine (they just get more weight).
_all_keys = [k for k in [config.GEMINI_API_KEY, config.GEMINI_API_KEY_2, config.GEMINI_API_KEY_3] if k.strip()]
pool = GeminiKeyPool(_all_keys)

if pool:
    print(f"[GeminiPool] {len(pool)} key(s) loaded — effective limit ~{len(pool) * 15} RPM")
else:
    print("[GeminiPool] No API keys configured — mock/offline mode")

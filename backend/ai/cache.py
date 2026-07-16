import hashlib
import json
import os
from config import CACHE_DIR


def get_file_hash(file_path: str) -> str:
    """SHA-256 hash of file contents. Same file = same hash = cache hit."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:20]


def load_cached_clauses(file_hash: str, document_type: str) -> list | None:
    """Return cached clause list if it exists, else None."""
    path = _cache_path(file_hash, document_type)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_cached_clauses(file_hash: str, document_type: str, clauses: list):
    """Save clause list to disk cache keyed by file hash + document type."""
    with open(_cache_path(file_hash, document_type), "w") as f:
        json.dump(clauses, f)


def _cache_path(file_hash: str, document_type: str) -> str:
    return os.path.join(CACHE_DIR, f"{file_hash}_{document_type}.json")

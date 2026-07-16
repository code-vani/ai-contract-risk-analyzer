"""
File Validator
==============
Performs pre-flight validation on uploaded documents before extraction begins.

Checks performed:
    1. File existence on disk
    2. File extension against the supported whitelist (.pdf, .docx)
    3. File size against configurable upper bound (default 20 MB)
    4. Zero-byte / empty file detection

This module is intentionally decoupled from the extraction logic so that
the FastAPI upload endpoint (Component 6) can run validation *before*
saving a temporary file to disk, failing fast on obviously bad uploads.
"""

import os
import logging
from typing import TypedDict, Optional

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".docx"}
MAX_FILE_SIZE_MB: int = 20

# ─── Return Type ──────────────────────────────────────────────────────────────

class ValidationResult(TypedDict):
    """Typed dictionary returned by validate_file."""
    is_valid: bool
    file_type: Optional[str]   # "pdf" | "docx" | None
    file_size_mb: Optional[float]
    error: Optional[str]


# ─── Public API ───────────────────────────────────────────────────────────────

def validate_file(file_path: str) -> ValidationResult:
    """
    Validate that a file is ready for text extraction.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the uploaded document.

    Returns
    -------
    ValidationResult
        A dictionary with ``is_valid``, ``file_type``, ``file_size_mb``,
        and ``error`` (None when valid).

    Examples
    --------
    >>> result = validate_file("contract.pdf")
    >>> if result["is_valid"]:
    ...     print(f"Ready to extract {result['file_type']} file")
    """

    # ── 1. Existence check ────────────────────────────────────────────────
    if not os.path.exists(file_path):
        logger.warning("Validation failed: file not found at %s", file_path)
        return ValidationResult(
            is_valid=False,
            file_type=None,
            file_size_mb=None,
            error=f"File not found: {file_path}",
        )

    # ── 2. Extension check ────────────────────────────────────────────────
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        logger.warning("Validation failed: unsupported extension '%s'", ext)
        return ValidationResult(
            is_valid=False,
            file_type=None,
            file_size_mb=None,
            error=(
                f"Unsupported file type: '{ext}'. "
                f"Accepted formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    # ── 3. Size check ─────────────────────────────────────────────────────
    size_bytes = os.path.getsize(file_path)
    size_mb = round(size_bytes / (1024 * 1024), 2)

    if size_bytes == 0:
        logger.warning("Validation failed: file is empty (0 bytes)")
        return ValidationResult(
            is_valid=False,
            file_type=ext.replace(".", ""),
            file_size_mb=0.0,
            error="File is empty (0 bytes)",
        )

    if size_mb > MAX_FILE_SIZE_MB:
        logger.warning(
            "Validation failed: file too large (%.2f MB > %d MB limit)",
            size_mb,
            MAX_FILE_SIZE_MB,
        )
        return ValidationResult(
            is_valid=False,
            file_type=ext.replace(".", ""),
            file_size_mb=size_mb,
            error=(
                f"File too large ({size_mb:.1f} MB). "
                f"Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
            ),
        )

    # ── 4. All checks passed ──────────────────────────────────────────────
    file_type = ext.replace(".", "")  # "pdf" or "docx"
    logger.info(
        "Validation passed: %s file, %.2f MB",
        file_type.upper(),
        size_mb,
    )

    return ValidationResult(
        is_valid=True,
        file_type=file_type,
        file_size_mb=size_mb,
        error=None,
    )

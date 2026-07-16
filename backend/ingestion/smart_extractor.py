"""
Smart Extractor — Hybrid Document Extraction Engine
====================================================
Primary extraction module for Component 1 of the Contract & SOW Risk Analyzer.

Strategy
--------
1. **DOCX files** → Always extracted via MarkItDown → returns clean Markdown.
2. **PDF files**  → MarkItDown text extraction is attempted first.
   - If ``words_per_page >= MIN_WORDS_PER_PAGE`` → digital PDF detected → return Markdown.
   - If ``words_per_page <  MIN_WORDS_PER_PAGE`` → scanned PDF detected →
     fall back to PyMuPDF page-to-JPEG conversion → return base64 image list.

Why Markdown?
-------------
LLMs are pre-trained heavily on Markdown-formatted web content. Sending
structured Markdown (with ``##`` headings and ``| table |`` syntax) to Gemini
produces drastically better clause extraction accuracy compared to dumping
raw unformatted text.

Output Contract
---------------
Every call to ``extract_smart()`` returns a dict with a ``mode`` field:

- ``mode="text"``  → ``content`` is a Markdown string.
- ``mode="image"`` → ``content`` is a list of ``{"page": int, "base64": str}`` dicts.
- ``mode="error"`` → ``content`` is ``None``; check ``error`` for the reason.

Component 2 reads ``mode`` first and dispatches accordingly.
"""

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Any

import fitz  # PyMuPDF — used only for image fallback and page counting

from markitdown import MarkItDown

from ingestion.file_validator import validate_file

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

# If a PDF averages fewer than this many words per page, it is treated as
# a scanned-image PDF and the image fallback path is triggered.
MIN_WORDS_PER_PAGE: int = 50

# Image conversion settings for the scanned-PDF fallback path.
# 150 DPI is sufficient for Gemini Vision to read printed text clearly.
# JPEG quality 40 keeps payload size manageable without sacrificing legibility.
IMAGE_DPI: int = 150
IMAGE_QUALITY: int = 40


# ─── Public API ───────────────────────────────────────────────────────────────

def extract_smart(file_path: str) -> dict[str, Any]:
    """
    Extract text or images from a PDF or DOCX file using a hybrid strategy.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the document.

    Returns
    -------
    dict
        Always contains a ``mode`` key (``"text"`` | ``"image"`` | ``"error"``).

        **Text mode** (digital PDF or DOCX)::

            {
                "mode": "text",
                "content": "## Section 4 — Payment Terms\\n...",
                "file_type": "pdf",
                "word_count": 3200,
                "page_count": 8,
                "words_per_page": 400
            }

        **Image mode** (scanned PDF)::

            {
                "mode": "image",
                "content": [{"page": 1, "base64": "...", "width": 1275, "height": 1650}],
                "file_type": "pdf",
                "page_count": 8
            }

        **Error mode**::

            {
                "mode": "error",
                "content": None,
                "error": "File is password protected — cannot read"
            }
    """

    # ── Step 1: Pre-flight validation ─────────────────────────────────────
    validation = validate_file(file_path)
    if not validation["is_valid"]:
        return _error_result(validation["error"])

    file_type = validation["file_type"]
    logger.info(
        "Starting extraction: %s (type=%s, size=%.2f MB)",
        os.path.basename(file_path),
        file_type.upper(),
        validation["file_size_mb"],
    )

    # ── Step 2: Route by file type ────────────────────────────────────────
    if file_type == "docx":
        return _extract_docx(file_path)

    if file_type == "pdf":
        return _extract_pdf(file_path)

    # Should never reach here because validate_file already checked extension,
    # but defensive programming never hurts.
    return _error_result(f"Unhandled file type: {file_type}")


# ─── DOCX Extraction ─────────────────────────────────────────────────────────

def _extract_docx(file_path: str) -> dict[str, Any]:
    """
    Extract text from a DOCX file using MarkItDown.

    DOCX files are never scanned images, so we always return text mode.
    MarkItDown preserves headings, numbered lists, and table structures
    as clean Markdown automatically.
    """
    try:
        md = MarkItDown()
        result = md.convert(file_path)
        text = result.text_content

        word_count = len(text.split())
        logger.info(
            "DOCX extraction complete: %d words extracted",
            word_count,
        )

        return {
            "mode": "text",
            "content": text,
            "file_type": "docx",
            "word_count": word_count,
            "page_count": None,       # DOCX format has no fixed page concept
            "words_per_page": None,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.exception("DOCX extraction failed for %s", file_path)
        return _error_result(f"Could not read DOCX file: {exc}")


# ─── PDF Extraction (Hybrid) ─────────────────────────────────────────────────

def _extract_pdf(file_path: str) -> dict[str, Any]:
    """
    Smart PDF extraction with automatic scanned-document detection.

    Attempt 1: MarkItDown text extraction (cheap, fast).
    Attempt 2: PyMuPDF page-to-JPEG conversion (expensive, but the only
               option for scanned documents).
    """

    # Count pages first — needed for both paths
    page_count = _count_pdf_pages(file_path)
    if page_count == 0:
        return _error_result("PDF has zero pages — file may be corrupted.")

    # Check for password protection before attempting extraction
    try:
        doc = fitz.open(file_path)
        if doc.is_encrypted:
            doc.close()
            return _error_result("File is password protected — cannot read")
        doc.close()
    except Exception as exc:
        return _error_result(f"Cannot open PDF: {exc}")

    # ── Attempt 1: MarkItDown text extraction ─────────────────────────────
    try:
        md = MarkItDown()
        result = md.convert(file_path)
        text = result.text_content
        word_count = len(text.split())
        words_per_page = word_count / max(page_count, 1)

        if words_per_page >= MIN_WORDS_PER_PAGE:
            logger.info(
                "PDF text extraction succeeded: %d words, %d pages (%.0f words/page)",
                word_count,
                page_count,
                words_per_page,
            )
            return {
                "mode": "text",
                "content": text,
                "file_type": "pdf",
                "word_count": word_count,
                "page_count": page_count,
                "words_per_page": round(words_per_page),
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }

        # Below threshold → likely a scanned document
        logger.warning(
            "Low text density detected: %.0f words/page (threshold=%d). "
            "Switching to image fallback for: %s",
            words_per_page,
            MIN_WORDS_PER_PAGE,
            os.path.basename(file_path),
        )

    except Exception as exc:
        logger.warning(
            "MarkItDown text extraction failed (%s). Trying image fallback.",
            exc,
        )

    # ── Attempt 2: Image fallback for scanned PDFs ────────────────────────
    try:
        images = _pdf_to_images(file_path)
        logger.info(
            "Image fallback succeeded: %d page(s) converted to JPEG",
            len(images),
        )
        return {
            "mode": "image",
            "content": images,
            "file_type": "pdf",
            "page_count": page_count,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.exception("Image fallback also failed for %s", file_path)
        return _error_result(f"Could not extract content from PDF: {exc}")


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _count_pdf_pages(file_path: str) -> int:
    """Count the number of pages in a PDF without extracting text."""
    try:
        doc = fitz.open(file_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def _pdf_to_images(file_path: str) -> list[dict[str, Any]]:
    """
    Convert each page of a PDF into a base64-encoded JPEG image.

    This is only invoked for scanned PDFs where text extraction yields
    insufficient content. The resulting base64 strings are sent to
    Gemini Vision for OCR-based clause extraction.

    Parameters
    ----------
    file_path : str
        Path to the PDF file.

    Returns
    -------
    list[dict]
        Each dict contains ``page`` (1-indexed), ``base64``, ``width``, ``height``.
    """
    zoom = IMAGE_DPI / 72  # 72 DPI is the PDF standard base resolution
    matrix = fitz.Matrix(zoom, zoom)
    images: list[dict[str, Any]] = []

    with fitz.open(file_path) as doc:
        for page in doc:
            pixmap = page.get_pixmap(matrix=matrix)
            jpeg_bytes = pixmap.tobytes(output="jpg", jpg_quality=IMAGE_QUALITY)
            b64_string = base64.b64encode(jpeg_bytes).decode("utf-8")

            images.append({
                "page": page.number + 1,  # 1-indexed for human readability
                "base64": b64_string,
                "width": pixmap.width,
                "height": pixmap.height,
            })

    return images


def _error_result(message: str) -> dict[str, Any]:
    """Build a standardised error response dict."""
    logger.error("Extraction error: %s", message)
    return {
        "mode": "error",
        "content": None,
        "error": message,
    }

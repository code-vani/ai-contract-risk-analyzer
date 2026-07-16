"""
Smart Extractor — CLI Runner
=============================
Command-line interface for testing the hybrid extraction engine on local files.

Usage:
    python backend/ingestion/run_extractor.py <file_path>

Examples:
    python backend/ingestion/run_extractor.py "C:/contracts/MSA.pdf"
    python backend/ingestion/run_extractor.py "C:/contracts/SOW.docx"
"""

import sys
import os
import json
import logging

# ── Path setup ────────────────────────────────────────────────────────────────
# smart_extractor uses `from ingestion.file_validator import ...` which requires
# backend/ on sys.path. We add it first so intra-backend imports resolve correctly.
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE_ROOT = os.path.dirname(_BACKEND_ROOT)
sys.path.insert(0, _WORKSPACE_ROOT)
sys.path.insert(0, _BACKEND_ROOT)

from ingestion.smart_extractor import extract_smart

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    # Fix Windows terminal encoding for Unicode characters in extracted text
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    if len(sys.argv) < 2:
        print("Usage: python backend/ingestion/run_extractor.py <file_path>")
        print("       Supports .pdf and .docx files.")
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        sys.exit(1)

    # ── Run extraction ────────────────────────────────────────────────────
    result = extract_smart(file_path)

    # ── Display results ───────────────────────────────────────────────────
    mode = result["mode"]
    print()
    print("=" * 70)
    print(f"  FILE:  {os.path.basename(file_path)}")
    print(f"  MODE:  {mode.upper()}")
    print("=" * 70)

    if mode == "error":
        print(f"\n  [ERROR] {result['error']}")

    elif mode == "text":
        print(f"  File Type:      {result['file_type'].upper()}")
        print(f"  Word Count:     {result['word_count']:,}")
        print(f"  Page Count:     {result.get('page_count') or 'N/A'}")
        print(f"  Words/Page:     {result.get('words_per_page') or 'N/A'}")
        print("-" * 70)
        print()

        # Show a preview (first 1500 characters) for quick verification
        content = result["content"]
        preview = content[:1500]
        print(preview)
        if len(content) > 1500:
            print(f"\n  ... [{len(content) - 1500:,} more characters truncated]")

    elif mode == "image":
        print(f"  File Type:      {result['file_type'].upper()}")
        print(f"  Page Count:     {result['page_count']}")
        print(f"  Images:         {len(result['content'])} page(s) converted")
        print("-" * 70)

        for img in result["content"]:
            b64_preview = img["base64"][:60]
            print(
                f"  Page {img['page']:>2}:  "
                f"{img['width']}x{img['height']}px  "
                f"base64[{len(img['base64']):,} chars]  "
                f"{b64_preview}..."
            )

    print()
    print("=" * 70)
    print("  Extraction complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()

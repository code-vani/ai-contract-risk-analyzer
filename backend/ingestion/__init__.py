"""
Backend Ingestion Package
=========================
Hybrid document extraction engine for the Contract & SOW Risk Analyzer.

Supports PDF and DOCX files with automatic scanned-document detection
and image fallback for OCR-dependent workflows.

Usage:
    from backend.ingestion.smart_extractor import extract_smart
    result = extract_smart("path/to/contract.pdf")
"""

from .smart_extractor import extract_smart
from .file_validator import validate_file

__all__ = ["extract_smart", "validate_file"]

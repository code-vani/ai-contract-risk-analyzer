"""Component 6, Tasks 2 & 3 — the /upload endpoint.

Accepts an MSA + SOW file, runs the full analysis pipeline, returns the combined
JSON, and always cleans up the temp files. Every error path returns a clear HTTP
status and message; nothing is allowed to crash the server.
"""

import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

import config
import pipeline

router = APIRouter()

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _validate_extension(file: UploadFile, label: str) -> None:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"{label} file must be a PDF or DOCX (got '{file.filename}').",
        )


def _save_temp(filename: str, data: bytes) -> str:
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(filename or "")[1].lower()
    path = os.path.join(config.UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as out:
        out.write(data)
    return path


@router.post("/upload")
async def upload(
    msa_file: UploadFile | None = File(None),
    sow_file: UploadFile | None = File(None),
):
    """Analyze an MSA + SOW pair and return risks, redlines, and the graph."""
    if not msa_file or not sow_file or not msa_file.filename or not sow_file.filename:
        raise HTTPException(status_code=400, detail="Please upload both MSA and SOW files")

    _validate_extension(msa_file, "MSA")
    _validate_extension(sow_file, "SOW")

    # Async reads so we don't block the event loop on file I/O.
    msa_path = _save_temp(msa_file.filename, await msa_file.read())
    sow_path = _save_temp(sow_file.filename, await sow_file.read())
    try:
        return pipeline.run_analysis(
            msa_path=msa_path,
            sow_path=sow_path,
            msa_name=msa_file.filename,
            sow_name=sow_file.filename,
        )
    except HTTPException:
        raise
    except Exception as exc:  # never leak a stack trace / crash the server
        message = str(exc).lower()
        if any(k in message for k in ("gemini", "api", "quota", "rate")):
            raise HTTPException(
                status_code=503,
                detail="AI service temporarily unavailable, please try again",
            )
        raise HTTPException(status_code=422, detail=f"Analysis failed: {exc}")
    finally:
        for path in (msa_path, sow_path):
            try:
                os.remove(path)
            except OSError:
                pass

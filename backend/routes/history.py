"""Component 6, Task 4 — history endpoints.

Thin wrappers over Component 9 (via the pipeline's indirection point) so past
analyses can be listed and re-opened.
"""

from fastapi import APIRouter, HTTPException

import pipeline

router = APIRouter()


@router.get("/history")
def history() -> list[dict]:
    """Return summaries of all past analyses, newest first."""
    return pipeline.list_history()


@router.get("/analysis/{analysis_id}")
def analysis(analysis_id: int) -> dict:
    """Return one full past analysis by id, or 404 if it does not exist."""
    result = pipeline.get_history(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return result

"""Extra endpoints the frontend needs: clause/risk search and redline decision."""

import json

from fastapi import APIRouter, Body, HTTPException

import pipeline

router = APIRouter()


@router.get("/search")
def search(q: str = "") -> list[dict]:
    """Full-text search across clauses and risks in all stored analyses.

    Returns up to 20 hits: [{analysis_id, section, kind, title, text}].
    """
    q = q.strip().lower()
    if len(q) < 2:
        return []

    hits: list[dict] = []
    for summary in pipeline.list_history():
        aid = summary["id"]
        analysis = pipeline.get_history(aid)
        if not analysis:
            continue

        for clause in analysis.get("clauses", []):
            text = (clause.get("text") or "").lower()
            title = clause.get("title") or clause.get("section_number") or ""
            if q in text or q in title.lower():
                hits.append({
                    "analysis_id": aid,
                    "section": clause.get("section_number") or clause.get("id"),
                    "kind": "clause",
                    "title": title,
                    "text": (clause.get("text") or "")[:200],
                })
                if len(hits) >= 20:
                    return hits

        for risk in analysis.get("results", []):
            desc = (risk.get("description") or "").lower()
            orig = (risk.get("original_text") or "").lower()
            if q in desc or q in orig:
                hits.append({
                    "analysis_id": aid,
                    "section": risk.get("clause_b_section") or risk.get("clause_a_section"),
                    "kind": "risk",
                    "title": risk.get("type", "Risk"),
                    "text": (risk.get("description") or "")[:200],
                })
                if len(hits) >= 20:
                    return hits

    return hits


@router.patch("/risks/{risk_id}/decision")
def update_decision(risk_id: str, body: dict = Body(...)) -> dict:
    """Persist an accept/reject decision for one redline suggestion.

    Walks all stored analyses to find the matching risk and updates its
    decision field in-place inside the results_json blob.
    Returns the updated risk or 404 if the id is unknown.
    """
    decision = body.get("decision")  # "ACCEPTED" | None

    from database.db import _Session
    from database.models import Analysis
    import sqlalchemy as sa

    with _Session() as session:
        rows = session.query(Analysis).order_by(Analysis.id.desc()).all()
        for row in rows:
            results = json.loads(row.results_json or "[]")
            updated = False
            for risk in results:
                if str(risk.get("risk_id") or risk.get("id") or "") == risk_id:
                    risk["decision"] = decision
                    updated = True
            if updated:
                row.results_json = json.dumps(results, default=str)
                session.add(row)
                session.commit()
                matched = next(r for r in results if str(r.get("risk_id") or r.get("id") or "") == risk_id)
                return matched

    raise HTTPException(status_code=404, detail=f"Risk '{risk_id}' not found")

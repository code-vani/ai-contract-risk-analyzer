"""Component 9 — SQLite-backed audit trail via SQLAlchemy.

Public API (must match mock_pipeline.py contract):
  save_analysis(record: dict) -> int
  get_all_analyses()          -> list[dict]
  get_analysis_by_id(id)      -> dict | None
"""

import json
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Analysis

# Database file lives at backend/contract_analyzer.db
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contract_analyzer.db")
_ENGINE = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_ENGINE, expire_on_commit=False)

# Required columns in the current schema — used to detect stale databases.
_REQUIRED_COLUMNS = {"results_json", "clauses_json", "graph_json", "blocker_count", "critical_count"}

import sqlalchemy as _sa

def _ensure_schema():
    """Create the analyses table if missing; recreate it if the schema is stale."""
    with _ENGINE.connect() as conn:
        existing_cols = {row[1] for row in conn.execute(_sa.text("PRAGMA table_info(analyses)"))}

    if not existing_cols:
        # Table does not exist at all — create_all will handle it.
        Base.metadata.create_all(_ENGINE)
        return

    missing = _REQUIRED_COLUMNS - existing_cols
    if not missing:
        # Schema is current — try adding any new optional columns safely.
        with _ENGINE.connect() as conn:
            for col, defn in [
                ("blocker_count",  "INTEGER NOT NULL DEFAULT 0"),
                ("critical_count", "INTEGER NOT NULL DEFAULT 0"),
            ]:
                if col not in existing_cols:
                    conn.execute(_sa.text(f"ALTER TABLE analyses ADD COLUMN {col} {defn}"))
            conn.commit()
        return

    # Schema is incompatible — drop and recreate (only dev/test data lives here).
    print(f"[DB] Schema outdated (missing: {missing}). Recreating analyses table.")
    Base.metadata.drop_all(_ENGINE)
    Base.metadata.create_all(_ENGINE)

_ensure_schema()


# --------------------------------------------------------------------------
# Public functions
# --------------------------------------------------------------------------

def save_analysis(record: dict) -> int:
    """Persist a completed analysis and return its auto-assigned integer id."""
    row = Analysis(
        timestamp    = Analysis.now_iso(),
        msa_filename = record.get("msa_filename", ""),
        sow_filename = record.get("sow_filename", ""),
        total_risks    = record.get("total_risks", 0),
        blocker_count  = record.get("blocker_count", 0),
        critical_count = record.get("critical_count", 0),
        high_count     = record.get("high_count", 0),
        medium_count   = record.get("medium_count", 0),
        low_count      = record.get("low_count", 0),
        status       = record.get("status", "COMPLETE"),
        results_json = json.dumps(record.get("results", []),  default=str),
        clauses_json = json.dumps(record.get("clauses", []),  default=str),
        graph_json   = json.dumps(record.get("graph",   {}),  default=str),
    )
    with _Session() as session:
        session.add(row)
        session.commit()
        return row.id


def get_all_analyses() -> list:
    """Return summary rows for every saved analysis, newest first."""
    with _Session() as session:
        rows = session.query(Analysis).order_by(Analysis.id.desc()).all()
        return [r.to_summary() for r in rows]


def get_analysis_by_id(analysis_id: int) -> dict | None:
    """Return the full analysis record, or None if the id does not exist."""
    with _Session() as session:
        row = session.get(Analysis, analysis_id)
        return row.to_full() if row else None

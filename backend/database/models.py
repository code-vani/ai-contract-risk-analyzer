"""SQLAlchemy ORM model for the Component 9 audit trail.

One row per analysis run. Blobs (results, clauses, graph) are stored as JSON
text so SQLite doesn't need any special JSON column support.
"""

import json

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class Analysis(Base):
    __tablename__ = "analyses"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    timestamp      = Column(String(64), nullable=False)
    msa_filename   = Column(String(256), nullable=False, default="")
    sow_filename   = Column(String(256), nullable=False, default="")
    total_risks    = Column(Integer, nullable=False, default=0)
    blocker_count  = Column(Integer, nullable=False, default=0)
    critical_count = Column(Integer, nullable=False, default=0)
    high_count     = Column(Integer, nullable=False, default=0)
    medium_count   = Column(Integer, nullable=False, default=0)
    low_count      = Column(Integer, nullable=False, default=0)
    status         = Column(String(32), nullable=False, default="COMPLETE")
    results_json   = Column(Text, nullable=False, default="[]")
    clauses_json   = Column(Text, nullable=False, default="[]")
    graph_json     = Column(Text, nullable=False, default="{}")

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def to_summary(self) -> dict:
        """Lightweight row — used by GET /history."""
        return {
            "id":             self.id,
            "timestamp":      self.timestamp,
            "msa_filename":   self.msa_filename,
            "sow_filename":   self.sow_filename,
            "total_risks":    self.total_risks,
            "blocker_count":  self.blocker_count,
            "critical_count": self.critical_count,
            "high_count":     self.high_count,
            "medium_count":   self.medium_count,
            "low_count":      self.low_count,
            "status":         self.status,
        }

    def to_full(self) -> dict:
        """Full record including blobs — used by GET /analysis/{id}."""
        return {
            **self.to_summary(),
            "results":  json.loads(self.results_json  or "[]"),
            "clauses":  json.loads(self.clauses_json  or "[]"),
            "graph":    json.loads(self.graph_json    or "{}"),
        }

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

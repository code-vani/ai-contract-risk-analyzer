"""FastAPI application entry point (Component 6, Task 1).

This is the central server that the React frontend talks to. It wires up CORS,
mounts the route modules, and exposes a simple health check. It does no AI work
itself — orchestration lives in `pipeline.py`, invoked by `routes/upload.py`.

Run locally:
    cd backend
    uvicorn main:app --reload
Then open http://localhost:8000/docs for the interactive API explorer.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from routes import history, risks, upload

# Component 2 owns ai/ledgar_loader.py; importing it warms the LEDGAR few-shot
# examples into memory once at startup (v2 change). Guarded so the server still
# boots standalone before that module exists (mock mode).
try:
    from ai.ledgar_loader import LEDGAR_EXAMPLES  # noqa: F401
except Exception:
    LEDGAR_EXAMPLES: list = []

app = FastAPI(
    title="Contract & SOW Risk Analyzer",
    description="Backend server that analyzes MSA + SOW documents for risks.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(history.router)
app.include_router(risks.router)


@app.get("/health")
def health() -> dict:
    """Liveness probe used by the frontend to check the server is up."""
    return {"status": "ok"}

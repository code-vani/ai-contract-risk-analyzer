import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY_2 = os.getenv("GEMINI_API_KEY_2", "")
GEMINI_API_KEY_3 = os.getenv("GEMINI_API_KEY_3", "")

UPLOAD_DIR = "uploads"
DATABASE_URL = "sqlite:///./contract_analyzer.db"

# Paths relative to the backend/ working directory
LEDGAR_DIR = os.path.join(
    os.path.dirname(__file__),
    "../Data_sets_hackathon/challenge-4-contract-sow-risk-analyzer/data/ledgar",
)
CONTRACTNLI_PATH = os.path.join(
    os.path.dirname(__file__),
    "../Data_sets_hackathon/challenge-4-contract-sow-risk-analyzer/data/contract_nli/contract-nli/train.json",
)
CUAD_DIR = os.path.join(
    os.path.dirname(__file__),
    "../Data_sets_hackathon/challenge-4-contract-sow-risk-analyzer/data/cuad",
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".clause_cache")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)


# ── Components 5 & 6 (Redline Generator + FastAPI Server) ────────────────────

def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# Gemini model for Component 5 redlines — overridable via env var
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")

# When True, Component 6 orchestrates with mock stubs for components not yet wired.
# Flip to False at full integration.
USE_MOCKS = _as_bool(os.getenv("USE_MOCKS"), True)

# Which stub set when USE_MOCKS is True:
#   "canned" -> fixed demo data (deterministic 6-issue demo)
#   "cuad"   -> reads the real uploaded file (tests C5/C6 on real text)
PIPELINE_SOURCE = os.getenv("PIPELINE_SOURCE", "canned").strip().lower()

# Origins allowed to call the API (React dev servers)
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]

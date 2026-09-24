"""Local runtime configuration. Relative paths resolve from the project root."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def configured_path(name, default):
    path = Path(os.environ.get(name, str(default))).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


DB_PATH = configured_path("RISKORA_DB_PATH", "data/riskora.db")
DATA_PATH = configured_path("RISKORA_DATA_PATH", "data/loan_default_full.csv")
ARTIFACTS_DIR = configured_path("RISKORA_ARTIFACTS_DIR", "ml/artifacts")
HOST = os.environ.get("RISKORA_HOST", "127.0.0.1")
PORT = int(os.environ.get("RISKORA_PORT", "8000"))

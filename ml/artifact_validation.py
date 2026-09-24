"""Checks for a complete artifact set before any database/server startup."""
from pathlib import Path

ARTIFACT_NAMES = ("riskora_model.joblib", "preprocessor.joblib", "model_metrics.json")


def validate_artifact_files(directory):
    directory = Path(directory)
    missing = [name for name in ARTIFACT_NAMES
               if not (directory / name).is_file() or (directory / name).stat().st_size == 0]
    if missing:
        raise FileNotFoundError(
            f"Missing or empty model artifacts: {', '.join(missing)}. "
            "Restore the complete artifact set or run python -m ml.train explicitly."
        )
    return tuple(directory / name for name in ARTIFACT_NAMES)

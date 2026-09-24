"""Validate the local runtime, then launch RISKORA without implicit retraining."""
import argparse
import sys


def main(argv=None):
    from backend.config import PORT, DATA_PATH
    parser = argparse.ArgumentParser(description="Start the local RISKORA workstation.")
    parser.add_argument("port", nargs="?", type=int, default=PORT)
    parser.add_argument("--check", action="store_true", help="Validate data and all model artifacts without writing to the database or starting HTTP.")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        if not DATA_PATH.is_file():
            raise FileNotFoundError(f"Dataset missing: {DATA_PATH}. Restore it or run python -m ml.generate_data explicitly.")
        from ml.infer import RiskInferenceEngine
        RiskInferenceEngine.get_instance()
        if args.check:
            print("Startup checks passed: dataset present; model, preprocessor and metrics validated.")
            return 0
        from backend.server import run_server
        run_server(args.port)
        return 0
    except (ImportError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Startup failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

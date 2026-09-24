"""
RISKORA — Application Launcher
Starts the unified full-stack server on http://localhost:8000.
Ensures database and trained model artifacts are present before starting.
"""

import os
import sys

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    artifacts_dir = os.path.join(base_dir, "ml", "artifacts")
    model_path = os.path.join(artifacts_dir, "riskora_model.joblib")
    data_path = os.path.join(base_dir, "data", "loan_default_full.csv")

    # Step 1: Ensure dataset exists
    if not os.path.exists(data_path):
        print("[SETUP] Synthesizing benchmark micro-lending dataset...")
        import ml.generate_data as gd
        df = gd.generate_benchmark_dataset(12000, seed=42)
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        df.to_csv(data_path, index=False)
        print(f"[SETUP] Created benchmark dataset ({len(df):,} records).")

    # Step 2: Ensure trained model artifacts exist
    if not os.path.exists(model_path):
        print("[SETUP] Training calibrated ML models...")
        import ml.train as mt
        mt.run_training_pipeline()

    # Step 3: Launch backend server
    from backend.server import run_server
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    run_server(port)

if __name__ == "__main__":
    main()

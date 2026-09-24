# RISKORA — micro-lending decision-support prototype

RISKORA combines a browser workstation, a Tornado JSON API, SQLite storage, and a calibrated scikit-learn model. The bundled 12,000-row dataset is synthetic. It supports an academic demonstration; real authentication, controlled funding approval, and reliable payment-ledger handling remain future milestones.

## First milestone: implemented

- Reproducible CPython 3.14 environment with pinned runtime dependencies.
- Startup validates all three model artifacts and checks inference compatibility before opening the database.
- One borrower-field schema across API, saved records, data quality, anomalies, and ML inference.
- Validated loan creation with parameterized SQL, UUIDs, and persistence of all supplied fields.
- One latest assessment per loan, deterministic timestamp tie-breaking, and corrected verification filters.
- Unchanged scenarios return zero risk difference; rate and term come from the actual scenario.
- Static serving is restricted to frontend files and public PNG/MP4 assets. The server binds to loopback by default and does not grant wildcard CORS access.
- Database-writing tests receive a fresh temporary database per test. Importing application modules no longer initializes storage.

## Install and run (Windows PowerShell)

Use CPython 3.14, the runtime used for local verification. Run these commands from the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe run.py --check
.\.venv\Scripts\python.exe run.py
```

Open `http://127.0.0.1:8000`. If the requested port is occupied, startup tries the next nine ports and prints the selected address. To request another port, use `run.py 8080`.

On Linux/macOS, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`. CI is configured for Windows and Linux; only Windows was executed locally for this milestone.

The reviewer-name entry screen is a demo identity label, not authentication. Keep this build local while authentication and payment controls are unfinished.

## Configuration

Environment variables are read at process startup. Relative paths resolve from the project root, regardless of the shell's working directory.

| Variable | Default |
|---|---|
| `RISKORA_HOST` | `127.0.0.1` |
| `RISKORA_PORT` | `8000` |
| `RISKORA_DB_PATH` | `data/riskora.db` |
| `RISKORA_DATA_PATH` | `data/loan_default_full.csv` |
| `RISKORA_ARTIFACTS_DIR` | `ml/artifacts` |

`.env.example` documents the values; `.env` files are not automatically loaded. For a separate demo database:

```powershell
$env:RISKORA_DB_PATH = "data/local-demo.db"
.\.venv\Scripts\python.exe run.py
```

An empty/new database is initialized and seeded only when starting the server. Existing data is preserved. `run.py --check` does not create or mutate a database.

## Model artifacts and dataset

Startup requires `riskora_model.joblib`, `preprocessor.joblib`, and `model_metrics.json`. Missing, empty, corrupt, incompatible-version, or structurally inconsistent artifacts cause startup to fail with a message. Startup never implicitly retrains or overwrites artifacts.

To intentionally regenerate the synthetic dataset or retrain (these commands overwrite their configured output files):

```powershell
.\.venv\Scripts\python.exe -m ml.generate_data
.\.venv\Scripts\python.exe -m ml.train
```

The removed sample CSV is no longer used as a fallback. The explorer returns 503 if the configured full dataset is unavailable.

The supplied artifacts were serialized with scikit-learn 1.9.1, which is pinned in `requirements.txt`. Their recorded test ROC-AUC is 0.7919, average precision 0.4023, and Brier score 0.0821 on the synthetic held-out split. Existing fixed explanation points are policy heuristics, not model-specific attribution. The explorer still uses a heuristic estimate rather than the calibrated model; that distinction is scheduled for the trustworthy-ML phase.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check app.js
```

Node is optional and only needed for the JavaScript syntax check. See `TESTING.md` for regression coverage. The test fixtures override the configured database path before initialization and remove their temporary databases after each test.

## API and loan creation

The new-loan API is working; the browser creation form belongs to the next workflow milestone. `POST /api/loans` requires `name` plus the eight required numeric fields described in `DATA_DICTIONARY.md`; optional demographic fields remain missing when omitted. Invalid input receives HTTP 400 without creating borrower/loan rows. See `API_DOCUMENTATION.md` for a complete example.

## Next milestones, in order

1. Complete workflow: explicit loan transitions, human review, preview versus commit, frontend loan creation and reliable restoration/report rendering.
2. Financial correctness: partial and duplicate payments, exact lender allocations, versioned schedules, actual outstanding exposure.
3. Trustworthy ML: accurate UI labels, prediction-source consistency, model-specific explanations and real-data evaluation.
4. Security/accountability: credentials, sessions, roles, authorization and reviewer-linked audit trails.
5. Deployment: migrations, health checks, logging, backup/restore and operational documentation.

`PROJECT_ANALYSIS.md` records the original audit before this milestone. The detailed architecture/model/demo documents also contain older claims and are not evidence that later milestones are implemented. This README, the current API/data dictionary, tests, and source describe the first-milestone behavior.

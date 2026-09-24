# RISKORA architecture

This diagram describes the current local prototype. Mermaid diagrams render directly on GitHub. Source references are relative to the repository root.

## Application and data flow

```mermaid
flowchart TB
    Reviewer["Reviewer<br/>Demo name entry, not authentication"]
    subgraph Browser["Browser workstation"]
        UI["index.html + styles.css + app.js<br/>Queue, assessment, scenarios, funding,<br/>repayments, exposure and reports"]
    end
    subgraph Runtime["Local Python runtime - Tornado"]
        Startup["run.py + backend/config.py<br/>Validate dataset and three model artifacts"]
        Static["PublicFileHandler<br/>Allowlisted frontend files and PNG/MP4 assets"]
        API["backend/server.py<br/>Same-origin JSON API"]
        Schema["backend/schema.py<br/>Shared borrower normalization and validation"]
        Quality["Data quality and anomaly rules"]
        Inference["ml/infer.py<br/>Preprocessor + calibrated HistGradientBoosting<br/>Default probability and risk band"]
        Funding["FundingService<br/>Lender allocation and concentration"]
        Repayment["RepaymentService<br/>Schedules and exact cent allocations"]
        Explorer["Dataset explorer<br/>Heuristic estimates, not model predictions"]
        Store["backend/database.py<br/>SQLite connection and transaction handling"]
    end
    subgraph Files["Local persistent files"]
        DB[("data/riskora.db<br/>Borrowers, loans, assessments,<br/>funding, schedules, payments, users and audit logs")]
        Artifacts["ml/artifacts<br/>riskora_model.joblib<br/>preprocessor.joblib<br/>model_metrics.json"]
        Dataset["data/loan_default_full.csv<br/>12,000 synthetic records"]
    end
    subgraph Offline["Explicit offline training - never automatic at startup"]
        Generate["python -m ml.generate_data"]
        Train["python -m ml.train<br/>Preprocessing, training, calibration and evaluation"]
    end
    Reviewer --> UI
    Startup --> API
    Startup --> Static
    Startup -. validates .-> Artifacts
    Startup -. checks presence .-> Dataset
    Static -->|HTML, JS, CSS and assets| UI
    UI <-->|HTTP JSON on loopback by default| API
    API --> Schema
    Schema --> Quality
    Schema --> Inference
    Artifacts --> Inference
    API --> Funding
    API --> Repayment
    API --> Explorer
    Dataset --> Explorer
    Artifacts -->|Saved evaluation metrics| API
    API -->|Persist or restore case state| Store
    Store <--> DB
    Generate --> Dataset
    Dataset --> Train
    Train --> Artifacts
```

Reports are assembled in the browser from the active case and restored API data. They are not separately persisted report documents. Borrower default risk and lender concentration are distinct outputs. Explanation points are policy rules, not SHAP values or model-specific attributions.

## Current reviewer workflow

```mermaid
flowchart LR
    Entry["Enter reviewer name"] --> Queue["Open saved loan"]
    Create["Create loan through API<br/>Browser form not yet implemented"] --> Queue
    Queue --> Assess["Validate data and assess risk"]
    Assess --> Report["View assessment report"]
    Assess --> Preview["Preview funding structure"]
    Preview --> Commit["Explicitly save funding"]
    Commit --> Schedule["Explicitly generate schedule"]
    Schedule --> Payment["Record full installment payment"]
    Payment --> Restore["Reload saved case and lender details"]
    Restore --> Exposure["Update exposure from paid principal"]
    Exposure --> Report
```

Changing funding controls creates a preview, not a saved commitment. Schedule controls require an explicit generate action. Recording a payment requires an existing schedule and the exact positive installment amount. Duplicate paid installments are rejected; loans with recorded payments cannot be reconfigured. Lender exposure subtracts paid principal allocations, including waterfall allocations.

These actions are local database operations: no money is transferred, and no external lender or payment provider is connected. Human approval stages are not yet enforced by a complete backend state machine.

## Boundaries and verification

- Startup validates the model, preprocessor and metrics before database initialization. Training is an explicit separate operation.
- Static serving excludes source, database, dataset and artifact files. API access is still unauthenticated; the reviewer label does not establish a trusted identity.
- `tests/support.py` isolates database-writing tests in temporary databases. `.github/workflows/tests.yml` runs startup checks and regressions on Windows and Linux.
- Partial payments, authenticated roles, reviewer-linked decision auditing, controlled approval transitions, schedule migrations and production operations remain future work.

See [README](README.md) for setup, [API documentation](API_DOCUMENTATION.md) for routes, and [testing notes](TESTING.md) for verification details.

# Review 1 — Dataset Demo Workflow

1. Start the app with `python -m http.server 8000` from the `RISKORA_V1_0_Updated` folder.
2. Open `http://localhost:8000`.
3. Open **Dataset Validation**.
4. Choose the downloaded `Loan_default.csv`.
5. RISKORA reads the CSV locally in the browser and applies the V1.0 deterministic scoring rules to every row.
6. Show the record count, High/Medium/Low distribution, validation snapshot and preview.
7. Explain that `Default` is historical ground truth and is not used to calculate the score.
8. Open **Loan Requests** → Rahul P → **Run RISKORA Analysis** to demonstrate the lender workflow.

## What to tell the faculty
"Version 1.0 is intentionally algorithmic. We first established an explainable baseline using the same attributes available in the historical dataset. The target column is kept separate to avoid data leakage. Once the baseline is validated, the next version can learn the weights and produce a calibrated probability of default using AI/ML."

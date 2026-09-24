# RISKORA API — first correctness milestone

Default base URL: `http://127.0.0.1:8000`. Requests use JSON objects and responses use JSON. Invalid JSON, invalid profile fields or conflicting aliases receive 400. Unknown loan identifiers receive 404. Internal exceptions are not exposed by the common error handler.

This build has a demo reviewer-name endpoint, not enforced authentication. Keep it local. Wildcard CORS has been removed. Only index.html, app.js, styles.css and PNG/MP4 files directly inside assets are publicly served; source files, datasets, models, SQLite and Git metadata are blocked.

## Loan creation

`POST /api/loans` creates a borrower and loan in one transaction and returns 201.

```json
{
  "name": "Example Borrower",
  "Age": 35,
  "Income": 480000,
  "LoanAmount": 100000,
  "CreditScore": 700,
  "DTIRatio": 0.25,
  "MonthsEmployed": 48,
  "NumCreditLines": 4,
  "InterestRate": 12.5,
  "LoanTerm": 24,
  "Education": "Bachelor's",
  "EmploymentType": "Salaried",
  "MaritalStatus": "Married",
  "HasMortgage": "No",
  "HasDependents": "Yes",
  "HasCoSigner": "No",
  "LoanPurpose": "Business"
}
```

Required fields are name and the eight numeric fields listed in DATA_DICTIONARY.md. Optional fields stay NULL when omitted. Response fields: `success`, UUID-based `loan_id` and `borrower_id`, `status`, and `data_quality`. A syntactically valid but contradictory profile is saved as NEEDS_VERIFICATION; invalid types/ranges/categories are rejected without writing rows.

## Current routes

| Method and route | Behavior |
|---|---|
| GET /api/health | Existing process-status response; dependency readiness checks are a later milestone |
| POST /api/auth/login | Accepts name and records a demo reviewer identity; no password/session enforcement |
| GET /api/loans | Queue; search by ID, borrower, amount or purpose; filter=all/high/analyzed/incomplete |
| POST /api/loans | Validated creation, 201 response as above |
| GET /api/loans/{id} | Saved borrower/loan and latest assessment, funding and schedule |
| POST /api/risk/analyze | Accepts loanId or standalone profile; saved values and request overrides use one schema |
| POST /api/risk/simulate | Requires baseLoanId; optional scenario object overrides canonical fields or aliases without writing records |
| POST /api/funding/optimize | Existing allocation calculator; providing loanId persists a structure |
| POST /api/repayment/generate | Existing amortisation calculator; providing loanId persists a schedule |
| POST /api/repayment/record | Existing payment recording, with known accounting limitations below |
| GET /api/exposure/portfolio | Risk distribution counts one latest assessment per loan; exposure-accounting corrections remain pending |
| GET /api/dataset/explorer | Paginated full synthetic CSV; literal search, risk filter and sorting; no sample fallback |
| GET /api/model/metrics | Returns configured model_metrics.json |

Queue rows no longer duplicate repeated assessments. `filter=incomplete` evaluates the saved profile's current data-quality readiness, including missing required fields and contradictions, even before an assessment exists. Unsupported filters receive 400. Latest records use timestamp and ID descending for deterministic ties.

## Analysis and scenarios

An ID-only analysis request is sufficient:

```json
{"loanId": "LR-1054"}
```

Canonical, camelCase and database snake_case fields are accepted through `backend/schema.py`. Request overrides are normalized before merging; Default and identifiers are excluded from the model inputs. Invalid supplied values receive 400. Missing inputs in existing records/sandbox requests remain visible in data-quality output while the inference adapter applies documented defaults.

The analysis response contains PD, score, risk band, review recommendation, policy-rule explanations, quality, anomalies and model metadata. Early review stages can become NEEDS_VERIFICATION or RISK_ASSESSED; re-analysis does not reset later statuses such as REPAYING. The complete workflow transition policy is not yet implemented.

An unchanged scenario must report zero deltas:

```json
{"baseLoanId": "LR-1054", "scenario": {}}
```

The scenario response has `base`, `scenario`, `comparison`, and a simulation notice. The indicative EMI uses the scenario's actual principal, interest rate and term, including zero interest. Simulations do not persist changes.

## Explorer

Parameters: `page` (minimum 1), `limit` (clamped 10–100), `search` (literal), `risk` (High/Medium/Low/all), `sort` (loan/credit/income/score). Invalid numeric pagination parameters receive 400. Empty searches return valid JSON with zero historical default rate for the empty subset. Missing configured data returns 503. Row PD and scores still use a heuristic estimate, not the trained model.

## Remaining contract work

Loan-detail funding/schedule response restoration, preview-versus-commit separation, reviewer authorization, immutable assessment snapshots, true dependency health checks, exact payment allocation, partial/duplicate/negative payment handling, and actual outstanding balances are later milestones. Successful responses from the legacy funding/payment endpoints do not establish that those controls exist.

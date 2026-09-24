# RISKORA testing

Run from the repository root using the pinned virtual environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe run.py --check
.\.venv\Scripts\python.exe -m pip check
node --check app.js
```

## Isolation

`backend.database` has no import-time storage writes. `tests/support.py` patches the database path to a new temporary SQLite file before initializing/seeding each database-writing test. Connections commit/roll back and explicitly close. The fixture restores the previous path and removes temporary files during cleanup, including on failure. Tests do not depend on accumulated demo data.

## Coverage

| Module | Tests | Coverage |
|---|---:|---|
| `tests/test_riskora.py` | 12 | ML sample profiles, quality, anomalies, funding, schedules and seed records |
| `tests/test_api_integration.py` | 10 | Existing API happy paths and payment endpoints |
| `tests/test_foundation.py` | 26 | Static file restrictions, creation/validation/rollback, mapping parity, scenarios, queue/filter correctness, startup/artifact checks and isolation |

Foundation regressions include:

- Private files and encoded traversal paths cannot be downloaded; frontend assets still load.
- No wildcard CORS grant.
- Names and education containing apostrophes persist safely; all profile fields survive creation/reload.
- Missing required values, non-finite numbers, invalid categories and malformed/non-object JSON are rejected without creating rows.
- ID-only and canonical input predictions, data quality and anomaly results match.
- Unchanged scenarios have zero delta; alternative aliases override saved fields; zero interest works.
- Unknown loans and invalid scenarios return useful 4xx responses.
- Repeated analyses and tied timestamps produce one latest queue/portfolio assessment per loan.
- Verification filters include missing and contradictory profiles without failing on null values.
- Re-analysis preserves REPAYING status; missing saved required fields route to NEEDS_VERIFICATION.
- Invalid quality inputs cannot crash or be reported verification-ready.
- Connections roll back on failure and close explicitly.
- Missing/empty/corrupt artifacts and invalid metrics fail startup; startup/import checks do not write storage or silently retrain.
- Literal explorer searches and empty results produce valid JSON; the deleted sample CSV is not a fallback.

## CI

`.github/workflows/tests.yml` installs pinned dependencies, checks their consistency, validates startup and runs tests on Windows/Linux with Python 3.14. Remote CI results require a push; adding the workflow does not mean CI has already executed.

## Boundaries

Local verification on 24 September 2026: **48 tests passed in 16.081 seconds** in a fresh pinned Windows virtual environment. Startup validation, dependency consistency, JavaScript syntax, and Git whitespace checks passed. The server-launch regression initialized a temporary database and served its six seeded loans. SHA-256 checks confirmed the application database and all three model artifacts remained unchanged. Remote CI has not been run.

Payment tests still describe the existing happy-path behavior, not validated accounting. Partial/duplicate/negative payment control, schedule versions, end-to-end browser workflow, real authentication, deployment load, and screen-reader behavior remain later work. The upstream Joblib/NumPy artifact loader can emit a NumPy shape-assignment deprecation warning; it is not a version mismatch or test failure.


## Frontend integration verification (2026-09-24)

Isolated browser QA confirmed report navigation, exact scenario baseline (credit 548,
zero PD difference), accessibility state, saved repayment terms, lender summaries after
payment, principal exposure before payment, clearing results when changing borrowers,
and mobile navigation without page-wide overflow. No browser console errors occurred.
The 50-test suite includes persistence and payment-guard regressions plus exact cent
allocation for all three repayment policies.

Funding previews do not save commitments. Schedule dropdowns do not save automatically.
Payments require a pre-existing schedule and exact installment amount; duplicate
payments are rejected and paid loans cannot be reconfigured. Partial payments and
full schedule-version migrations remain future work. Reviewer names are labels,
not authentication; this is still a local demonstration, not a production lending system.

# Testing and verification

The supported automated runner is Python's built-in unittest. Tests use temporary SQLite databases; never run manual API demonstrations against a database whose records must remain unchanged. Use the pinned Python 3.14 environment from README.

## Commands

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe run.py --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check app.js
node --check integration.js
```

On Linux/macOS, replace the interpreter path with `.venv/bin/python`. To run one area, use `python -m unittest tests.test_ora_integration -v`. Node syntax checks do not execute browser logic or prove accessibility.

`pytest.ini` restricts optional pytest discovery to `tests/` and excludes extracted archives and generated outputs. pytest is not a runtime dependency and is not used by CI; install it separately if choosing that runner. The unittest command above remains the baseline reproduction command.

## Database isolation

`tests/support.py` supplies `IsolatedDatabaseMixin`. Each database-backed test creates a TemporaryDirectory, patches `backend.database.DB_PATH`, initializes a new schema, seeds demo cases and creates its own authenticated test account/session. Cleanup restores the patch and removes the temporary directory. Test passwords are fixtures, not application credentials.

Startup tests use separate subprocess environment paths. Importing modules and running `run.py --check` must not create a database. The default-migration test builds its own temporary historical/runtime paths and checks preservation. No test requires a user to delete an existing runtime file.

To verify isolation independently, hash the application database before and after running the suite while the normal server is stopped or idle. Do not compare a database concurrently changing from real user actions and assume every difference came from tests.

## Coverage map

| Test module | Main checks |
|---|---|
| `test_foundation.py` | Static allowlist, full profile creation/reload, invalid-create rollback, JSON errors, normalization parity, unchanged scenarios, aliases, queue deduplication, incomplete filtering, DB lifecycle, stage preservation and artifact/startup failures |
| `test_api_integration.py` | Health, queue/detail, analysis, scenario, funding, repayment, explorer and payment HTTP contracts |
| `test_riskora.py` | Model bands, data quality, anomaly rules, funding concentration, amortization, twice-monthly dates and allocation reconciliation |
| `test_workflow.py` | Saved contract restoration, payment guards and exact allocations for each schedule policy |
| `test_ora_integration.py` | Login/logout, CSRF/origin controls, roles, expiry, one-time setup, approval snapshots, ORA evidence, edit invalidation, partial/duplicate receipts, approved terms, closure and migration preservation |

The suite contains 63 tests at this documentation revision. The documentation release run on 10 October 2026 completed with all 63 passing in 29.148 seconds. This is a count of tests, not a claim of 100% code or behavioral coverage. Dependency consistency, artifact startup validation and both JavaScript syntax checks also passed locally.

## Financial assertions

Tests check that a payment is positive and within the remaining installment, that sub-cent and nonfinite values fail, and that stale schedules cannot accept new receipts. Matching idempotency retries do not add a second payment; conflicting reference reuse fails.

For every accepted receipt, the allocated lender totals equal the receipt to the cent. Principal and interest reconcile within each allocation. Partial payments accumulate correctly, final payments close the loan and outstanding principal reaches zero. Schedules cannot be replaced after receipts. Legacy unlinked receipts remain in storage and explicitly require reconciliation.

These tests do not cover real bank settlement, refunds, reversals or write-offs because those features are not implemented. They also do not prove all possible concurrent interleavings; broader concurrency testing remains planned work.

## Manual browser verification

The integration walkthrough used a separate temporary database and checked:

- First administrator setup, login and logout.
- Creation of a complete borrower and assessment from saved fields.
- Human approval tied to the assessment, followed by explicit fractional funding.
- Monthly schedule generation and a partial receipt.
- Saved funding, schedule and outstanding principal after page reload.
- ORA source labels and low-risk report wording.
- A 390 by 844 mobile viewport with navigation and no horizontal overflow.
- Browser console output during the exercised path.

The example in DEMO_GUIDE.md produced a INR 1,000 receipt split into INR 909.71 principal and INR 90.29 interest, with INR 39,090.29 outstanding. A screenshot is retained at `output/integration/RISKORA_ORA_integration.png`. It is evidence of one exercised state, not proof that every screen or accessibility path is correct.

Browser checks are manual and are not part of the current GitHub Actions workflow. Add automated browser tests for slow responses, case-switch races, session expiry, keyboard focus, validation errors and print output before claiming full end-to-end regression coverage.

## CI

`.github/workflows/tests.yml` runs on pushes and pull requests with a Windows/Linux matrix and Python 3.14. It installs pinned runtime dependencies, runs `pip check`, validates startup artifacts, executes unittest and checks both JavaScript files using Node 22.

A local passing run does not prove that a new remote Actions run passed. Inspect the GitHub run after pushing. Dependency-install availability, operating-system differences and remote runner failures can still affect CI.

## Documentation and PDF verification

Install optional `requirements-docs.txt` and run `python generate_final_review_pdf.py`. The generator reads selected maintained guide sections and model metadata without touching SQLite. Verify Markdown relative links, output existence and extracted PDF text. Render every page to check margins, table wrapping, diagram labels, headers and page breaks; text extraction alone cannot detect overlap or clipping.

The generator supports a fixed report date so repeated generation can use the same visible date. The generated document is a snapshot: regenerate after changes to source documentation or metrics. The older Review 2 PDF remains labelled historical.

## Release checklist

1. Inspect the Git diff for credentials, runtime files and unintended incoming ZIP content.
2. Run dependency, startup, regression and syntax checks.
3. Exercise the affected browser flow if UI or API behavior changed.
4. Update API, schema and model claims against implementation.
5. Regenerate and visually inspect the current review PDF.
6. Verify that runtime databases and temporary outputs remain ignored.
7. Commit source and intended deliverables, push normally and check remote status.

Tests are a boundary for verified claims, not a replacement for review. Record failures and untested areas explicitly instead of describing the whole application as production-ready.

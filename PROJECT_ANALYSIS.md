# Project analysis and work plan

This assessment describes the integrated repository, not every feature in the received ZIP. The project has a usable local reviewer workflow and a synthetic-data model demonstration. It is not yet a validated production lending service.

## Current system

The frontend is plain HTML, CSS and JavaScript, served by the same Tornado process as the API. SQLite persists borrowers, loans, assessments, decisions, funding, schedules, receipts and accounts. The shared borrower schema keeps create/edit, stored analysis and simulation aligned. Trusted joblib artifacts provide inference without retraining at startup.

OraAgent features were adapted into this system rather than copied as a second backend. Login, intake forms, review records and an ORA brief are integrated with existing IDs and financial services. The integration avoids fabricated bank/identity evidence and keeps the saved model band authoritative.

## Repository responsibilities and maintenance risks

| Area | Current responsibility | Maintenance consideration |
|---|---|---|
| `app.js`, `index.html`, `styles.css` | Main workstation and reports | Large view functions make state changes harder to isolate |
| `integration.js` | Auth and new workflow dialogs | Keep event/state ownership explicit between both scripts |
| `backend/server.py` | Main HTTP handlers and orchestration | Split only after preserving API contracts with tests |
| `backend/integration.py` | Account, edit, review and audit routes | Route factory depends on shared BaseHandler |
| `backend/schema.py` | Single borrower normalization contract | Update tests, forms and dictionary together |
| `backend/services/` | Quality, anomaly, funding, schedule and receipt logic | Keep financial invariants independent of presentation |
| `backend/database.py` | Schema, migration and seed | Additive migration needs a managed upgrade plan |
| `ml/` | Synthetic generation, training and inference | Preserve artifact/data/code provenance per release |
| `data/` | Synthetic CSV and historical demo database | Live accounts/receipts must stay in ignored runtime storage |
| `tests/` | Service and HTTP regressions | Browser automation and concurrency coverage remain limited |
| `output/` | Review PDFs and integration evidence | Label historical reports to avoid stale claims |
| `tmp/` | Ignored extracts, logs and working files | Never make runtime imports depend on it |

Dependency versions are pinned, Python 3.14 is specified, startup validates all three model artifacts and CI is configured for Windows/Linux. `.env.example` documents actual variables without introducing unused secrets or settings. A separate optional documentation dependency file keeps PDF generation out of the server installation.

## Confirmed improvements in the integration

Loan creation validates and persists one normalized profile. The queue selects one latest assessment, and verification filtering uses current completeness and contradictions. Saved analysis and unchanged scenarios share a baseline. Static serving is restricted. Reviewer identity and assessment snapshots are recorded. Explicit human approval gates funding, and schedule generation uses approved terms.

New payments reject malformed, negative, duplicate-conflicting and excessive amounts. Partial receipts reconcile in cents and update principal exposure from actual allocations. Schedule versions are protected after payment. Reload restores saved finance details, and reports use the actual model band. Ambiguous historical receipts remain preserved and visibly require reconciliation.

These improvements are covered by the tests named in TESTING.md. They do not imply that every concurrency, accessibility or operational scenario is tested.

## Remaining limitations

| Limitation | Consequence |
|---|---|
| Synthetic training and test data | No real-world underwriting accuracy claim |
| Fixed policy explanations | No model-specific attribution or causal explanation |
| Deterministic ORA brief | No independent document verification or agent reasoning |
| Legacy unlinked receipts | Certain historical balances remain unknown until reconciliation |
| REAL amounts and JSON finance structures | API invariants are essential; not a full accounting ledger |
| No reversals/refunds/write-offs | Corrections to actual financial events lack a supported flow |
| Single process and synchronous work | Throughput and latency need measurement |
| Process-local login limiter | Not shared across workers or restarts |
| No password-reset/account-disable workflow | Account lifecycle requires further design |
| Additive startup migration | No managed rollback or historical schema test matrix |
| Public health is descriptive | Does not prove database readiness or backup health |
| No supported HTTPS deployment package | Local success is not deployment readiness |
| Browser checks are manual | UI regressions are not all caught by CI |
| Historical tracked demo database | Keep it a fixture; never replace it with a live database |

## Work in priority order

### 1. Correctness and accounting

Build a reviewed legacy-receipt reconciliation tool that preserves original events and records every correction. Define reversal, refund and early-payoff behavior before extending payment handling. Add adversarial concurrent-request tests around edit/assess/review/fund/schedule operations. Measure and close race windows rather than claiming all multi-user writes are fully serialized.

Completion means each receipt and correction has a traceable relationship to a schedule and lender allocation, and concurrent submissions cannot bypass stage or balance rules. Continue using exact-cent invariants and immutable event records where possible.

### 2. Complete the reviewer workflow

Decide whether separate persisted Draft and Submitted stages are necessary, then define the allowed transition table before changing UI labels. Add account recovery, account disable/session revocation controls and a supported reconciliation view. Add automated browser journeys for login, incomplete intake, approval, payment, refresh and print report.

Completion means a reviewer can finish or explicitly resolve every supported case state without direct database edits, and reload or session expiry does not lose committed work or leave stale displays.

### 3. Trustworthy ML

Define a real outcome and observation window, validate an appropriate dataset, split temporally and compare to simple baselines. Put preprocessing inside calibration folds. Evaluate subgroup behavior and probability calibration, choose thresholds against measured costs and add explanations appropriate to the actual trained model. Version code, data and artifact hashes together.

Completion means every claimed metric has a documented cohort, period, method and limitation, and a reviewer can identify the source of each score and explanation. Synthetic model results remain labelled until replaced by validated evidence.

### 4. Security and accountability

Review threat boundaries for remote use, configure TLS and trusted proxy behavior, add account lifecycle management and improve audit completeness. Review dependency updates against model serialization compatibility. Protect database files and backups, and document retention and access ownership. Add abuse, session and origin tests for the intended deployment topology.

Completion means unauthorized requests cannot retrieve private data or change workflow state, account changes are traceable, and backup/restoration does not silently revive unintended access. No compliance certification should be inferred from these engineering controls.

### 5. Deployment and maintenance

Provide a supported process-manager or container configuration, readiness checks, structured operational logs, managed schema migrations and a tested backup/restore runbook. Benchmark expected workload and choose a database/worker design based on measurements. Add automated release checks for documentation links and PDF regeneration.

Completion means a fresh host can be installed, upgraded, monitored and restored using documented commands, with recorded verification of the restored application and model revision.

## Future features after the foundation

Lender integrations, document extraction, drift monitoring and agent-assisted review should use the same validation and permission boundaries. Any future agent must submit proposals or evidence through supported APIs and retain explicit human approval for lending and financial actions. Adding a chatbot before accounting and workflow gaps are resolved would not address the highest-priority needs.

## Evidence and references

Implementation sources are `backend/schema.py`, `backend/server.py`, `backend/integration.py`, `backend/database.py`, `backend/security.py`, the services directory, `ml/train.py` and `ml/infer.py`. Evaluation values come from `ml/artifacts/model_metrics.json`. Tests and browser evidence are described in [TESTING.md](TESTING.md); integration provenance is in [INTEGRATION.md](INTEGRATION.md). No external regulatory approval or production certification is asserted.

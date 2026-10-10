# OraAgent integration — 10 October 2026

## Source and integration choice

The supplied `RiskOra_OraAgent-main.zip` contains a separate FastAPI application under `riskora/`, a browser frontend, another model pipeline, CSV files and review documents. RISKORA already has a working Tornado application, a shared input schema and regression coverage. Running both backends would create two incompatible loan stores and prediction contracts.

The useful workflows were adapted into the existing application. The ZIP was inspected in `tmp/incoming`; its entry scripts and serialized models were not executed. The incoming archive remains unchanged. Its SHA-256 is `ee76c66477ad06efa4fcef5b3042b17abc0e722a843f2593e2adb2f2266f29cd`.

| Incoming component | Integrated result |
|---|---|
| `riskora/backend/security.py` | Adapted salted password hashing and login into `backend/security.py`; replaced hardcoded signing secrets/custom JWTs with revocable random sessions. |
| Borrower application routes and frontend form | Added create/edit dialogs driven by the existing shared schema; persistence uses the current borrower/loan tables. |
| `services/risk_service.py` ORA analysis | Adapted as `backend/services/ora_service.py`, based on the saved calibrated assessment and actual snapshot. Removed invented identity, bank, device, psychometric and mandate evidence. |
| Reviewer/marketplace workflow | Added explicit review records linked to the current assessment and authenticated reviewer before funding. |
| Funding and repayment services | Kept the established tested allocation engine; integrated strict stage guards, approved terms, schedule IDs and exact-cent partial receipts. |
| Report/certificate features | Extended the existing printable report with ORA, reviewer decisions, receipts and outstanding principal. No compliance certificate is asserted. |

The incoming FastAPI runner, incompatible integer-ID database schema, alternate model binaries, mock lender marketplace, negotiation routes, fabricated TLS/domain responses and legal compliance assertions were not copied into the runtime. Mock bank/eNACH/psychometric values would otherwise appear to be verified facts. The existing model's risk bands remain authoritative; ORA does not apply a contradictory 300–900 bureau-style score.

## New modules

- `backend/security.py`: salted PBKDF2 passwords and hashed revocable sessions.
- `backend/integration.py`: first-use setup, account roles, shared form schema, profile edits, decisions and review history.
- `backend/services/ora_service.py`: evidence brief and input digest.
- `backend/services/payment_service.py`: integer-cent proportional partial receipts against remaining scheduled principal/interest allocations.
- `integration.js`: login, borrower intake, review, account and payment dialogs.
- `tests/test_ora_integration.py`: security, lifecycle, snapshot, payment and migration regressions.

The original source of each adapted feature is identified above. The integration does not introduce an LLM, a bank connection, autonomous credit approval or an external payment processor.

## Data compatibility

Database changes are additive. Existing borrowers, loans, schedules and receipts are retained. Separate account/session tables avoid treating historical reviewer labels as authenticated credentials. Assessment snapshots and reviewer IDs are nullable for historical records; new assessments populate both.

New receipt records carry a schedule ID and unique idempotency reference. Older receipts cannot be safely assigned to a schedule merely from an installment number, especially where that number appears repeatedly. Those loans display a reconciliation warning and block new payments. Their original receipts remain available in SQLite for review. No historical receipt was deleted or guessed away.

The default mutable database now lives under ignored `data/runtime/`. On first default startup it is copied from the former database. Tests and browser checks use separate temporary databases; the original application database remains unchanged by the integration checks.

## Behaviour contracts

- Editing an unfunded profile invalidates its displayed assessment and decision eligibility. History is retained.
- Approval requires the latest assessment ID, complete valid model inputs and a nonempty review note.
- Funding requires approved status and the saved amount. The saved model supplies the risk band.
- Schedule generation uses saved lender positions and approved loan terms. It cannot replace a schedule after any payment.
- Partial receipts split integer cents across remaining scheduled lender principal/interest amounts. Every receipt and final installment reconciles exactly.
- A duplicate reference with the same loan, installment and amount is a no-op; a conflicting use is rejected.
- Exposure comes from stored receipt allocations. Model risk remains separate from lender concentration.
- Reports use the current risk band, not approval-label string matching. This corrects an old low-risk report that incorrectly showed a high-risk warning.

See README for startup and TESTING.md for verification results. Production deployment and real-data model validation remain separate work.

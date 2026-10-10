# Demonstration guide

Use this walkthrough for a faculty review of the integrated application. It demonstrates a complete recorded workflow using synthetic inputs. Do not describe funding or payment buttons as real bank transactions.

## Prepare a clean demonstration

Install and run the checks in README. Use a separate runtime database so repeated demonstrations do not change the normal reviewer database:

```powershell
$env:RISKORA_DB_PATH = 'data/runtime/review-demo.db'
.\.venv\Scripts\python.exe run.py 8010
```

A custom path avoids importing old historical receipts. The server creates the schema and six example loans when empty. Open the printed address on the same computer, complete the one-time administrator setup and sign in. Do not display or include the password in screenshots. Use an existing demonstration account if this database was already initialized.

Before presenting, check `python run.py --check`, browser connectivity and the loan queue. Keep the model card available so metrics can be explained from their source. The bundled historical review PDF predates integration; use the current root review document for current behavior.

## Main demonstration: create through partial repayment

### 1. Login and describe the roles

Show the login screen. Explain that accounts are persisted, sessions expire, and a viewer cannot modify loans. An administrator can create a reviewer or viewer account. Authentication is enforced by the API as well as the interface.

### 2. Create a complete borrower

Use the create-loan action and enter this synthetic profile:

| Field | Value |
|---|---|
| Borrower name | Faculty demo borrower |
| Age | 38 |
| Annual income | INR 720,000 |
| Loan amount | INR 40,000 |
| Credit score | 782 |
| Employment months | 72 |
| Credit lines | 2 |
| Annual interest | 9.5% |
| Loan term | 12 months |
| DTI | 0.16 |
| Education | Master's |
| Employment | Salaried |
| Marital status | Married |
| Dependents, mortgage, co-signer | Yes for each |
| Purpose | Education |

Save and note the generated loan ID. Reopen it from the queue to show persistence. Explain that 0.16 means 16% DTI and that income is annual, not monthly. The backend uses one schema regardless of entry point.

### 3. Assess the saved profile

Run risk assessment. With the current artifact, the previously checked example produced approximately 0.52% PD, a display score of 5 and LOW risk. These values identify this artifact/profile combination; do not promise them after retraining.

Show input-quality results alongside risk. Explain that quality is about completeness and consistency, whereas PD is a model output. Point out that driver/protective points are fixed policy indicators. The synthetic training data does not validate actual lending decisions.

### 4. Explain ORA and record human review

Open the decision/review section. ORA summarizes saved input evidence and the model result. Its snapshot digest helps identify an input version; it does not prove income or identity. Record approval with a meaningful note such as: “Complete synthetic demonstration inputs reviewed; proceeding with the workflow exercise.”

Show the recorded reviewer and decision. Explain that the review is linked to the latest assessment. A model recommendation alone cannot commit funding.

### 5. Preview and commit funding

Select fractional funding with three lenders. Discuss concentration before saving. The current sample structure uses about 43.48%, 33.33% and 23.19% participation. Commit the funding explicitly. Confirm that the borrower PD and band remain unchanged.

The lenders are generated demonstration positions. This does not connect to a lender marketplace or disburse the requested amount.

### 6. Generate a repayment schedule

Choose monthly repayment and pro-rata allocation with a suitable start date. The principal, rate and term must remain the approved INR 40,000, 9.5% and 12 months. Explain that the schedule is a plan and has a saved version ID.

The checked example's first installment was INR 3,507.34. Rounding may adjust a final installment to reconcile the plan. Show each installment's principal, interest and lender allocation rather than only the total EMI.

### 7. Record a partial receipt

Record INR 1,000 against the first installment using a new reference such as `faculty-demo-20261010-001`. Do not reuse that reference for another payment. The checked example allocated INR 909.71 to principal and INR 90.29 to interest, leaving INR 39,090.29 outstanding principal.

Explain why the outstanding balance did not fall by the full INR 1,000: interest is received cash but does not repay principal. The installment should show PARTIAL and the loan should show REPAYING. The remaining installment amount is INR 2,507.34.

### 8. Reload and report

Refresh the page and reopen the same case. Confirm the saved funding, schedule, receipt and outstanding principal remain present. Navigate to exposure and the report. Print the case report or save it as PDF through the browser. The report should describe the LOW band appropriately and include current saved financial details.

End by signing out. The authenticated shell should no longer be available. This completes the path from account access to a persisted repayment event and report.

## Short negative demonstrations

| Demonstration | Expected result | What it proves |
|---|---|---|
| Omit an optional input, save and assess | Needs verification; approval blocked | Missing data is surfaced |
| Supply a negative loan amount | Validation error | Backend enforces numeric rules |
| Analyze an unchanged scenario | Zero delta | Saved baseline and mapping agree |
| Try to fund before approval | Conflict response | Human review gate |
| Try to edit a funded profile | Conflict response | Approved financial terms protected |
| Retry identical payment reference | No second receipt | Idempotent recording |
| Reuse reference with another amount | Conflict response | Reference cannot disguise a different payment |
| Try to pay more than remaining installment | Validation error | Overpayment blocked |
| Try to regenerate schedule after payment | Conflict response | Receipt history remains linked |
| Access source/database through static URL | Not served | Restricted static routing |

Use a fresh demo case for destructive-looking attempts so the main presentation case remains clear. Automated tests are the more reliable place to demonstrate all invalid combinations.

## If the demonstration is interrupted

Read the actual server URL if port 8010 was occupied. A login timeout requires signing in again, not recreating the database. If a request times out, reopen the case before repeating a write. Retry receipts with the same reference. For historical demo cases with reconciliation warnings, explain the limitation and use a newly created case; do not delete their old receipts to remove the warning.

After stopping the demo server, remove the temporary environment setting with `Remove-Item Env:RISKORA_DB_PATH`. Keep or securely archive the demo database locally. Runtime databases and credentials must not be committed.

# RISKORA API

All business routes require the `riskora_session` cookie. Every POST must include `Content-Type: application/json` and `X-Riskora-Request: 1`. Browser calls must be same-origin. Unauthenticated requests return 401, forbidden actions 403, invalid inputs 400, missing records 404 and invalid workflow transitions 409. VIEWER accounts can read; REVIEWER and ADMIN accounts can perform case actions. Only ADMIN can create accounts.

## Accounts

| Route | Purpose |
|---|---|
| GET `/api/health` | Public startup/service status |
| GET `/api/auth/setup` | Public first-use setup status |
| POST `/api/auth/setup` | One-time loopback-only administrator creation: `username`, `password` |
| POST `/api/auth/login` | Credentials: `username`, `password`; sets HttpOnly SameSite session cookie |
| GET `/api/auth/me` | Current account ID, username and role |
| POST `/api/auth/logout` | Revoke current session |
| POST `/api/auth/accounts` | Admin creates `username`, `password`, `role` (ADMIN/REVIEWER/VIEWER) |

Usernames have 3–80 characters; passwords have 12–200. Password hashing uses PBKDF2-HMAC-SHA256 with 600,000 iterations and random salts. Sessions last eight hours. Login is limited to ten attempts per source IP in five minutes in the local server process.

## Borrower and risk workflow

| Route | Contract |
|---|---|
| GET `/api/schema` | Numeric bounds, integer flags, categories and required intake fields |
| GET `/api/loans` | Queue, `search` and `filter=all/high/analyzed/incomplete` |
| POST `/api/loans` | `name` and canonical/aliased profile; returns `loan_id`, `borrower_id` |
| GET `/api/loans/{id}` | Saved profile, current assessment, funding, schedule, decision, ORA and ledger |
| POST `/api/loans/{id}/edit` | Full replacement profile plus `name`; only before funding; requires reassessment |
| POST `/api/risk/analyze` | `loanId` assesses saved fields; without ID, assesses an unsaved profile |
| POST `/api/risk/simulate` | `baseLoanId` and `scenario` overrides; no persistence |
| POST `/api/loans/{id}/review` | `assessment_id`, `decision`, `note`; latest assessment required |
| GET `/api/loans/{id}/audit` | Case events and authenticated review history |

Review decisions: `APPROVED`, `REJECTED`, `NEEDS_VERIFICATION`. Notes must contain 5–2000 characters. Approval requires complete model inputs and passing input-quality rules. It records the human review; input-quality rules do not verify external documents.

Example complete loan body:

```json
{
  "name": "Example borrower", "Age": 38, "Income": 720000,
  "LoanAmount": 40000, "CreditScore": 782, "DTIRatio": 0.16,
  "MonthsEmployed": 72, "NumCreditLines": 2, "InterestRate": 9.5,
  "LoanTerm": 12, "Education": "Master's", "EmploymentType": "Salaried",
  "MaritalStatus": "Married", "HasDependents": "Yes", "HasMortgage": "Yes",
  "HasCoSigner": "Yes", "LoanPurpose": "Education"
}
```

Fields required at intake: Income, LoanAmount, CreditScore, DTIRatio, LoanTerm, MonthsEmployed, NumCreditLines and InterestRate. Other omissions are stored as missing and prevent approval until resolved. LoanAmount must have at most two decimal places. The schema endpoint supplies authoritative ranges/categories.

Saved risk analysis cannot silently override stored profile values. Use the edit route for real corrections or simulation for hypothetical changes. ORA uses the same saved model risk band; its digest identifies the normalized snapshot and is not a verification certificate.

## Funding, schedules and payments

POST `/api/funding/optimize`: `amount`, `mode=auto/single/fractional`, `lenderCount=2..6`. Omit `loanId` for a preview. Including `loanId` commits only if the loan is approved and amount equals the saved principal. The saved assessment supplies borrower risk. Existing commitments cannot be overwritten.

POST `/api/repayment/generate`: `loanId`, `principal`, `rate`, `term`, optional `startDate` (YYYY-MM-DD), `scheduleType=monthly/bi-monthly/flexible`, `allocationPolicy=pro-rata/largest-first/earliest-first`. Saved funding supplies lender positions. Principal, rate and term must match the approved loan. The response includes schedule `id`; another schedule is allowed only before any receipts.

POST `/api/repayment/record`:

```json
{
  "loanId": "RETURNED_LOAN_ID", "scheduleId": 1, "installmentNum": 1,
  "amount": "1000.00", "idempotencyKey": "receipt-reference-unique-001"
}
```

Use the actual saved loan ID and current schedule ID. The amount must be positive, have at most two decimal places and not exceed the remaining installment amount. The payment reference must have 8–100 characters. Retries must use the same reference: matching submissions are a no-op, conflicting reuse returns 409. Partial receipts return PARTIAL; full installments return PAID. All installments paid moves the loan to CLOSED.

Loan details include `ledger.received`, `principal_paid`, `outstanding_principal`, `lender_principal_paid` and `payment_count`. Historical receipts without schedule linkage set `requires_reconciliation=true`, provide a warning and return null outstanding principal. Additional payments on such loans are blocked.

## Analytics

- GET `/api/exposure/portfolio`: latest portfolio risk bands and recent funding structures.
- GET `/api/dataset/explorer`: labelled synthetic data with separate heuristic estimates; `search`, `risk`, `sort`, `page`, `limit`.
- GET `/api/model/metrics`: stored evaluation artifact.

The printable report is assembled in the browser from saved loan details; there is no remote certificate-generation or money-transfer API. See [integration notes](INTEGRATION.md).

## Request conventions and response handling

The API is unversioned and served from the same origin as the UI. JSON bodies must be objects. Send the session cookie returned by login on later calls; there is no bearer-token API. Do not store passwords in scripts committed to Git. Most successful operations return 200; loan creation and account setup/creation return 201. Errors contain `error` and `status` fields. Clients should show the server's reason and keep the user's unsaved input when correction is possible.

| Status | Meaning | Client action |
|---|---|---|
| 400 | Invalid body, field, category, amount or query | Correct input; do not retry unchanged |
| 401 | No valid session | Sign in and reload saved state |
| 403 | Role, origin, request-header or setup restriction | Check access and request origin |
| 404 | Unknown record or unavailable static path | Check ID/path |
| 409 | Stage, assessment, schedule or receipt conflict | Reload the case and resolve the conflict |
| 429 | Login attempt limit | Wait for the five-minute window to pass |
| 500 | Unexpected server failure | Inspect local logs; do not assume a write failed before retrying |

A network timeout does not prove a POST was not committed. Loan creation has no client idempotency token, so inspect the queue before repeating it. Receipt recording does have an idempotency reference; retry with the same reference and original values.

## Worked local API journey

This PowerShell example uses an existing reviewer account and an interactive credential prompt. It keeps the session in memory instead of writing a cookie file. Run against a separate demonstration database, because these calls create a loan and recorded financial events.

```powershell
$base = 'http://127.0.0.1:8000'
$headers = @{ 'X-Riskora-Request' = '1' }
$credential = Get-Credential -Message 'Existing RISKORA account'
$login = @{ username=$credential.UserName; password=$credential.GetNetworkCredential().Password } | ConvertTo-Json
Invoke-RestMethod "$base/api/auth/login" -Method Post -Headers $headers -ContentType 'application/json' -Body $login -SessionVariable session
$login = $null
function Send-RiskoraPost($path, $payload) {
    Invoke-RestMethod "$base$path" -Method Post -Headers $headers -WebSession $session -ContentType 'application/json' -Body ($payload | ConvertTo-Json -Depth 10)
}
$profile = @{
    name='API demonstration borrower'; Age=38; Income=720000; LoanAmount=40000
    CreditScore=782; DTIRatio=0.16; MonthsEmployed=72; NumCreditLines=2
    InterestRate=9.5; LoanTerm=12; Education="Master's"; EmploymentType='Salaried'
    MaritalStatus='Married'; HasDependents='Yes'; HasMortgage='Yes'
    HasCoSigner='Yes'; LoanPurpose='Education'
}
$created = Send-RiskoraPost '/api/loans' $profile
$loanId = $created.loan_id
Send-RiskoraPost '/api/risk/analyze' @{ loanId=$loanId }
$case = Invoke-RestMethod "$base/api/loans/$loanId" -WebSession $session
Send-RiskoraPost "/api/loans/$loanId/review" @{
    assessment_id=$case.assessment.id; decision='APPROVED'
    note='Demonstration inputs reviewed; synthetic workflow exercise.'
}
Send-RiskoraPost '/api/funding/optimize' @{
    loanId=$loanId; amount=40000; mode='fractional'; lenderCount=3
}
Send-RiskoraPost '/api/repayment/generate' @{
    loanId=$loanId; principal=40000; rate=9.5; term=12
    scheduleType='monthly'; allocationPolicy='pro-rata'; startDate='2026-11-01'
}
$case = Invoke-RestMethod "$base/api/loans/$loanId" -WebSession $session
# Inspect the returned repayment object and use its current id.
$case.repayment | ConvertTo-Json -Depth 3
Send-RiskoraPost '/api/repayment/record' @{
    loanId=$loanId; scheduleId=$case.repayment.id; installmentNum=1
    amount='1000.00'; idempotencyKey=('demo-' + [guid]::NewGuid().ToString())
}
Invoke-RestMethod "$base/api/loans/$loanId" -WebSession $session
Send-RiskoraPost '/api/auth/logout' @{}
```

For a real retry, retain the original payment payload and reuse it exactly; the fresh GUID above is only for a new demonstration receipt. First-use setup is a separate one-time POST to `/api/auth/setup` from loopback, with username/password and the same request header. It creates the initial administrator but does not replace the login step.

## Detailed read semantics

The queue response contains `count` and `loans`. `search` matches loan ID, borrower name, amount and purpose. `high` uses the latest visible HIGH assessment, `analyzed` requires a visible assessment, and `incomplete` evaluates current input readiness. Latest-assessment selection prevents one queue row per historical assessment. A profile reset to REQUEST_RECEIVED does not show a stale risk result.

Loan detail returns the saved borrower and loan fields together with decoded assessment, funding, repayment, review decision, ORA and ledger objects. Missing stages can be null. The frontend must clear a previous case's panels when those objects are absent. Old review history remains history; it does not authorize a new assessment automatically.

The audit endpoint returns up to 100 case events and review decisions joined to reviewer usernames. Generic successful API-action audit entries may use an endpoint path as entity ID and therefore are not all included in a loan-specific audit query. Audit records are application evidence, not an immutable external log.

Portfolio exposure aggregates current stored loan/assessment/funding information. Dataset explorer pagination and filtering concern synthetic CSV rows, not saved applications. The metrics endpoint reads saved evaluation metadata; it does not perform fresh training or evaluation.

## Simulation contract

```json
{"baseLoanId":"RETURNED_LOAN_ID","scenario":{"LoanAmount":35000,"DTIRatio":0.14}}
```

Only supplied canonical or aliased scenario fields replace the saved baseline. An empty scenario must reproduce the baseline and return zero difference. Simulation does not edit the borrower, save approval, commit funding or change repayment terms. Use the profile-edit endpoint for actual corrections before funding.

## Financial edge cases

`bi-monthly` means twice monthly in this application, with dates on the 5th and 20th; it does not mean one payment every two months. `flexible` adds a six-day due window. These are demonstration scheduling policies, not jurisdiction-specific loan contracts.

New payment references are globally unique across stored receipts. A matching duplicate returns success with `duplicate=true` and the existing payment ID. A different loan, installment or amount under the same reference is rejected. A stale schedule ID is rejected for a new receipt; clients should restore the saved plan after refresh.

Partial payment allocations are proportional to the remaining scheduled lender principal/interest buckets, with integer-cent remainders distributed deterministically. This is not an interest-first collections policy. Overpayments are rejected rather than automatically applied to a later installment. Refunds, reversals, early payoff, fees and external settlement callbacks are not implemented.

See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for units and all field ranges, and [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for persistence and legacy limitations.

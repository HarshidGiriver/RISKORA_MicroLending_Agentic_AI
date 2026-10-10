# Data dictionary

`backend/schema.py` is the source of truth for borrower fields across create/edit, saved analysis, inference and simulation. `GET /api/schema` exposes numeric constraints, categories and required intake fields to the frontend. The model has 16 raw inputs: nine numeric and seven categorical.

## Required intake and complete assessment

Eight numeric fields are required to save a new application. Age and seven categorical fields may be absent at intake, but approval requires all 16 values plus passing consistency rules. A borrower name is also required for creation/editing: a trimmed nonempty string of 1–200 characters. Name and server-generated IDs are not model predictors.

Blank strings and JSON null are treated as missing. Numeric booleans, nonfinite values, invalid ranges, fractional integers and unknown categories are rejected. Categories are matched case-insensitively and stored in canonical form. Yes/No fields also accept true/false and 1/0 aliases. Unrecognized extra keys are ignored by profile normalization; clients should still send only documented fields.

## Numeric fields

| Field | Unit | Inclusive range | Integer | Required at intake | Inference fallback |
|---|---|---|---|---|---|
| `Age` | years | 18 to 95 | Yes | No | 35 |
| `Income` | annual INR | 1 to 5000000 | No | Yes | 450000 |
| `LoanAmount` | INR, at most 2 decimals | 0.01 to 5000000 | No | Yes | 120000 |
| `CreditScore` | input credit score | 300 to 850 | Yes | Yes | 650 |
| `MonthsEmployed` | months | 0 to 948 | Yes | Yes | 36 |
| `NumCreditLines` | count | 0 to 25 | Yes | Yes | 4 |
| `InterestRate` | annual percent, 9.5 means 9.5% | 0 to 100 | No | Yes | 12.5 |
| `LoanTerm` | months | 1 to 120 | Yes | Yes | 36 |
| `DTIRatio` | ratio, 0.16 means 16% | 0 to 1.5 | No | Yes | 0.32 |

## Categorical fields

| Field | Allowed values | Inference fallback |
|---|---|---|
| `Education` | High School, Bachelor's, Master's, PhD | Bachelor's |
| `EmploymentType` | Salaried, Self-employed, Contract, Unemployed | Salaried |
| `MaritalStatus` | Single, Married, Divorced | Married |
| `LoanPurpose` | Business, Education, Home, Auto, Other | Business |
| `HasMortgage` | Yes, No | No |
| `HasDependents` | Yes, No | No |
| `HasCoSigner` | Yes, No | No |

## Accepted field names

Use canonical names in new clients. Existing aliases remain supported. Supplying two aliases with different normalized values is an error, not last-write-wins behavior. Scenario overrides are normalized separately before they replace baseline fields.

| Canonical field | Other accepted names |
|---|---|
| `Age` | `age` |
| `Income` | `income`, `annualIncome` |
| `LoanAmount` | `loan_amount`, `loanAmount`, `amount` |
| `CreditScore` | `credit_score`, `creditScore`, `credit` |
| `MonthsEmployed` | `months_employed`, `monthsEmployed`, `empMonths` |
| `NumCreditLines` | `num_credit_lines`, `numCreditLines`, `creditLines` |
| `InterestRate` | `interest_rate`, `interestRate`, `rate` |
| `LoanTerm` | `loan_term`, `loanTerm`, `term` |
| `DTIRatio` | `dti_ratio`, `dtiRatio`, `dti` |
| `Education` | `education` |
| `EmploymentType` | `employment_type`, `employmentType`, `employment` |
| `MaritalStatus` | `marital_status`, `maritalStatus` |
| `HasMortgage` | `has_mortgage`, `hasMortgage` |
| `HasDependents` | `has_dependents`, `hasDependents` |
| `LoanPurpose` | `loan_purpose`, `loanPurpose`, `purpose` |
| `HasCoSigner` | `has_cosigner`, `hasCoSigner`, `hasCosigner` |

## Missing values and quality rules

Fallbacks exist only in the inference adapter; they are not a claim that a missing input is known. Database storage, input snapshots and quality results retain the missingness. A model result produced using fallbacks must be read alongside its missing-data warnings.

The quality score combines required-field completeness (65 points), optional-field completeness (15 points) and a base 20 points, subtracting 5 per warning and 12 per contradiction, then rounding and clamping to 10–100. Tiers are excellent at 88+, acceptable at 70+, degraded at 50+, otherwise critical. Approval uses `verification_ready`, not only this numeric score.

Contradictions include employment tenure longer than `(Age - 16) * 12`, an unemployed category with positive employment months, and zero credit lines with DTI above 0.35. Warnings include income below INR 50,000 and a loan above 2.5 times annual income without a co-signer. Verification readiness requires no missing inputs, warnings or contradictions. This is internal input consistency, not bank or identity verification.

## Dataset-only fields and derived features

| Field | Meaning | Used as predictor? |
|---|---|---|
| `LoanID` | Synthetic row identifier | No |
| `Default` | Synthetic binary label, 1=default | Target only |
| `LoanToIncome` | LoanAmount / annual Income, denominator protected at 1 | Derived predictor |
| `MonthlyBurdenRatio` | Principal per month / monthly income, denominator protected at 1 | Derived predictor |

The dataset contains 12,000 generated rows. Its values are not real customer observations. Application borrower/loan IDs (`BRW-...`, `LR-...`) identify SQLite records independently of dataset LoanID values.

## Assessment outputs

| Field | Unit/meaning |
|---|---|
| `probability_of_default` | Fraction from 0 to 1, returned rounded to four decimal places |
| `probability_pct` | Percentage, returned rounded to two decimal places |
| `risk_score` | Display transformation bounded to 5–99, not a bureau score |
| `risk_level` | LOW, MEDIUM or HIGH from model thresholds |
| `data_quality_score` | Input-quality score, not model accuracy |
| `review_level` | Suggested review intensity; does not authorize funding |
| `impact_pts` | Fixed policy-rule points; not additive model contributions |
| `model_version` | Artifact metadata version attached to saved assessment |
| `input_snapshot_json` | Normalized saved inputs, potentially including missing values |

Band calculations use the underlying probability before display rounding. A printed probability near a boundary may round to 8.00% or 20.00%; the stored band remains the classification returned by the model engine.

## Funding, schedule and receipt terms

`amount` and `principal` are INR. Schedule `rate` is annual percent and `term` is months. `lenderCount` is an integer from 2 to 6 for fractional participation; single funding has one position. Concentration describes lender participation and is independent of borrower default probability.

`scheduleId` is the active repayment_schedules row ID. `installmentNum` is a positive whole installment number. Payment `amount` accepts a number or decimal string with at most two places. `idempotencyKey` is a client reference of 8–100 characters and must be reused for retries of the same receipt.

`received` includes principal and interest. `principal_paid` includes only principal allocations. `outstanding_principal` is original principal less actual principal receipts; it can be null when legacy records need reconciliation. Null does not mean zero. `PARTIAL` and `PAID` describe installment receipt status, while `REPAYING` and `CLOSED` describe loan workflow status.

## Source ownership

The reviewer supplies borrower fields. The model supplies PD and band. Policy code supplies rule indicators. Funding and repayment services supply simulated plans. Recorded receipts supply actual application-ledger balances. ORA labels those sources and computes an input digest; it does not verify income, identity, account ownership or a payment against an external institution.

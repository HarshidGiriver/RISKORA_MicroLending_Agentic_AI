# RISKORA V1.0 — Deterministic Risk Algorithm

## Purpose
Provide a transparent baseline risk score for Review 1 before AI/ML integration.

## Inputs
- CreditScore
- Income
- LoanAmount
- DTIRatio
- MonthsEmployed
- NumCreditLines
- InterestRate
- LoanTerm
- HasMortgage
- HasDependents
- HasCoSigner

## Scoring rules
| Factor | Condition | Points |
|---|---|---:|
| Credit score | <450 | +25 |
| | 450–549 | +20 |
| | 550–649 | +12 |
| | 650–749 | +5 |
| | >=750 | +0 |
| DTI | >=0.45 | +20 |
| | 0.35–0.449 | +15 |
| | 0.25–0.349 | +8 |
| Loan / annual income | >=3.0 | +15 |
| | 2.0–2.999 | +10 |
| | 1.0–1.999 | +5 |
| Employment duration | <12 months | +10 |
| | 12–23 months | +6 |
| Credit lines | >=8 | +8 |
| | 5–7 | +4 |
| Interest rate | >=18% | +8 |
| | 12–17.99% | +4 |
| Loan term | 48–60 months | +6 |
| | 36–47 months | +3 |
| No co-signer | Yes | +5 |
| No mortgage | Yes | +2 |
| Dependents | Yes | +2 |

## Risk bands
- 0–30: Low
- 31–60: Medium
- 61–100: High

## Missing data
Missing values are reported separately as information gaps. They are not automatically converted into risk points.

## Important validation rule
`Default` is never used to calculate the score. After scoring, the historical Default field can be compared against the risk bands to inspect baseline behaviour.

## Future AI/ML stage
A later version can learn the scoring weights from historical data and return calibrated probability of default, subject to train/test separation, class-imbalance handling, feature validation, explainability and fairness checks.

# RISKORA — Data Dictionary & Feature Specifications

---

## Overview
This document specifies the schema, data types, permissible ranges, handling strategies, and model impacts for all 18 features in the micro-lending risk framework.

---

## 1. Feature Specifications

| Field Name | Data Type | Permissible Range / Values | Description | Imputation / Missing Strategy | Model Role & Impact |
|---|:---:|---|---|---|---|
| `LoanID` | `String` | Regex: `^LID-\d{5}$` or `^LR-\d{4,6}$` | Unique identifier for the loan request. | Excluded from modeling; used for relational joins and audit logs. | Identifier only. |
| `Age` | `Integer` | $18 \le \text{Age} \le 95$ | Chronological age of applicant at time of application. | Median imputation ($35$) if missing. Flagged in Data Quality audit. | Continuous numerical; non-linear interaction with employment tenure. |
| `Income` | `Float` | $₹50,000 \le \text{Income} \le ₹50,00,000$ | Verified annual gross earnings in Indian Rupees (INR). | Mandatory. If missing, applicant flagged as Incomplete / Critical Gaps. | Continuous numerical; high protective impact when loan-to-income is low. |
| `LoanAmount` | `Float` | $₹10,000 \le \text{LoanAmount} \le ₹50,00,000$ | Requested loan principal in INR. | Mandatory. Default from active case. | Continuous numerical; primary denominator for exposure sizing and repayment schedules. |
| `CreditScore` | `Integer` | $300 \le \text{CreditScore} \le 850$ | Bureau credit score (CIBIL / Experian scale). | If missing, routed to thin-file protocol with $+15$ penalty points. | Continuous numerical; highest individual coefficient. Prime scores ($>720$) mitigate default hazard. |
| `MonthsEmployed` | `Integer` | $0 \le \text{MonthsEmployed} \le 600$ | Continuous months of employment in current role/business. | Imputed to $0$ if missing. Flagged in Data Quality audit. | Continuous numerical; stability indicator. Tenures $<12$ months increase default hazard. |
| `NumCreditLines` | `Integer` | $0 \le \text{NumCreditLines} \le 25$ | Number of currently open, active credit lines/loans. | Mode imputation ($4$). | Continuous numerical; high lines ($>8$) indicate credit saturation. |
| `InterestRate` | `Float` | $5.0\% \le \text{InterestRate} \le 36.0\%$ | Offered annual interest rate (APR). | Median ($12.5\%$) if unstated. | Continuous numerical; higher APR reflects risk-based pricing and increases debt service burden. |
| `LoanTerm` | `Integer` | $\{12, 18, 24, 36, 48, 60\}$ months | Loan contract duration in months. | Default to $36$ months. | Continuous numerical; longer tenures ($48–60$) expand cumulative default hazard window. |
| `DTIRatio` | `Float` | $0.00 \le \text{DTIRatio} \le 1.50$ | Debt-to-Income: monthly debt commitments divided by monthly income. | Mode ($0.32$) if unstated. | Continuous numerical; ratios $>0.45$ heavily increase default hazard. |
| `Education` | `Category` | `High School`, `Bachelor's`, `Master's`, `PhD` | Highest verified educational credential. | Imputed to `Bachelor's`. One-hot encoded. | Categorical; stability proxy in digital lending contexts. |
| `EmploymentType` | `Category` | `Salaried`, `Self-employed`, `Contract`, `Unemployed` | Primary employment arrangement. | Mode (`Salaried`). One-hot encoded. | Categorical; `Unemployed` triggers high risk flags. `Contract` represents elevated variability. |
| `MaritalStatus` | `Category` | `Single`, `Married`, `Divorced` | Declared civil marital status. | Mode (`Married`). One-hot encoded. | Categorical; contextual cash-flow indicator. |
| `HasMortgage` | `Category` | `Yes`, `No` | Indicates existing active residential mortgage liability. | Imputed to `No`. Binary encoded. | Binary indicator; interaction with DTI ratio. |
| `HasDependents` | `Category` | `Yes`, `No` | Presence of financial dependents. | Imputed to `No`. Binary encoded. | Binary indicator; increases household expenditure floor. |
| `LoanPurpose` | `Category` | `Business`, `Education`, `Home`, `Auto`, `Other` | Declared use of micro-loan proceeds. | Mode (`Business`). One-hot encoded. | Categorical; micro-enterprise productive loans exhibit different loss profiles than consumer loans. |
| `HasCoSigner` | `Category` | `Yes`, `No` | Presence of a verified secondary repayment guarantor. | Imputed to `No`. Binary encoded. | Binary indicator; `Yes` provides major risk mitigation and protective factor. |
| `Default` | `Binary` | $0$ (Non-Default), $1$ (Default) | Historical ground truth outcome. | Supervised training target only. | **TARGET VARIABLE ONLY**. Strictly isolated from inference feature vector. |

---

## 2. Engineered Features

| Derived Feature | Formula | Purpose |
|---|---|---|
| `LoanToIncome` | $\text{LoanAmount} / \max(\text{Income}, 1)$ | Quantifies capital loss exposure relative to annual repayment capacity. |
| `MonthlyBurdenRatio` | $(\text{LoanAmount} / \text{LoanTerm}) / (\text{Income} / 12)$ | Estimates monthly principal cash outflow as a fraction of monthly gross income. |

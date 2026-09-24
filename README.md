# RISKORA — AI-Assisted Risk-Based Framework for Digital Micro-Lending

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/API-Tornado%206.5-green.svg)](https://www.tornadoweb.org/)
[![ML Model](https://img.shields.io/badge/ML-Calibrated%20HistGBM-orange.svg)](https://scikit-learn.org/)
[![Tests](https://img.shields.io/badge/Tests-21%20Passed-brightgreen.svg)](tests/)

RISKORA is an institutional-grade, explainable AI/ML risk intelligence and decision-support platform designed for digital micro-lending. It unifies borrower credit risk prediction, data quality verification, anomaly detection, syndicated funding optimization, and waterfall repayment management into an auditable credit underwriting workstation.

---

## Key Capabilities

### 1. Calibrated Machine Learning Risk Scoring
- Powered by a scikit-learn **HistGradientBoosting** classifier calibrated via **Sigmoid Platt Scaling** (5-Fold Stratified CV).
- Predicts true statistical **Probability of Default (PD)** mapped to an institutional risk score ($0–100$) and risk bands (**Low**, **Medium**, **High**).
- Tested on 1,800 unseen loan records: **ROC-AUC 0.7919**, **PR-AUC 0.4023**, and **Brier Score Loss 0.0821**.
- **Proven Default Rate Separation**: Observed default rates escalate monotonically from **3.75%** (Low Risk) to **13.41%** (Medium Risk) to **36.20%** (High Risk).

### 2. Local Explainability & Feature Attribution
- Real-time feature attribution identifying specific upward pressure drivers (+pts) and protective mitigators (-pts).
- Clear regulatory disclosure distinguishing statistical correlation from deterministic causal laws.

### 3. Data Quality & Anomaly Detection Engines
- **Data Quality Engine**: Evaluates completeness and validity across 8 required and 7 optional fields, independent of default risk.
- **Anomaly Engine**: Multivariate statistical scan detecting extreme leverage spikes, demographic contradictions, and data entry inconsistencies.

### 4. Syndicated Funding Optimizer
- Single-Lender vs. Fractional Multi-Lender syndication.
- Computes capital commitments and **Herfindahl-Hirschman Index (HHI)** concentration metrics.
- Highlights the foundational risk distinction: *Fractional funding distributes lender concentration risk; it does not alter borrower default probability.*

### 5. Multi-Schedule Amortisation & Waterfall Repayment
- Generates schedules across **Fixed Monthly**, **Fixed Bi-Monthly (24 periods/yr)**, and **Flexible Payment Windows**.
- Applies multi-lender waterfall policies: **Pro-Rata Allocation** (default), **Largest Contribution First (LCF Waterfall)**, and **Earliest Funding First (FIFO)**.
- Penny-perfect balance reconciliation ensuring the final balance closes at exactly ₹0.00.
- Interactive payment recording updating persistent ledger entries in real time.

### 6. Interactive What-If Scenario Lab
- Stress-test loan amounts, credit scores, and DTI ratios against the live ML inference service without altering saved loan records.

### 7. Dataset Explorer & Target Leakage Prevention
- Server-side paginated, filterable, and sortable explorer across 12,000 benchmark loan records.
- Ground truth `Default` is strictly isolated for post-hoc validation and never fed into feature matrices.

---

## System Architecture

```
RISKORA Workstation (HTML5 / ES6+ / CSS3)
        │
        ▼  [Asynchronous REST API / JSON]
Tornado Backend Gateway (Port 8000)
   ├── Auth Service (/api/auth/login)
   ├── Loan Service (/api/loans)
   ├── Risk Intelligence (/api/risk/analyze & /simulate)
   ├── Funding Optimizer (/api/funding/optimize)
   ├── Repayment Engine (/api/repayment/generate & /record)
   ├── Exposure Monitor (/api/exposure/portfolio)
   └── Dataset Explorer (/api/dataset/explorer & /model/metrics)
        │
        ├── ML Engine (Calibrated HistGradientBoosting + Platt Scaling)
        ├── Data Quality Engine & Anomaly Detector
        └── Relational Storage (SQLite: data/riskora.db)
```

---

## Quick Start Guide

### Prerequisites
- Python 3.10+ (Python 3.12 verified)
- Standard Python libraries (`scikit-learn`, `pandas`, `numpy`, `tornado`, `joblib`)

### 1. Launch the Platform
From the `RISKORA_V1_0_Updated` directory:
```powershell
python run.py
```
This automatically verifies benchmark data and model artifacts, initializes the database, and starts the workstation.

### 2. Access the Workstation
Open your web browser to:
```
http://localhost:8000
```
Enter your reviewer name (e.g. `Dr. Reviewer`) to enter the workstation.

### 3. Run Automated Tests
```powershell
python -m unittest discover tests
```
Executes all 21 unit and integration tests (**100% pass rate in ~4.6s**).

---

## Documentation Index

| Document | Purpose |
|---|---|
| [**ARCHITECTURE.md**](ARCHITECTURE.md) | Complete architectural blueprint with 9 detailed Mermaid diagrams. |
| [**ML_PIPELINE.md**](ML_PIPELINE.md) | Machine learning pipeline, benchmark evaluation, calibration, and metrics. |
| [**MODEL_CARD.md**](MODEL_CARD.md) | Formal model card covering intended uses, performance, fairness, and limits. |
| [**DATA_DICTIONARY.md**](DATA_DICTIONARY.md) | Schema, data types, value ranges, and handling strategies for all 18 features. |
| [**API_DOCUMENTATION.md**](API_DOCUMENTATION.md) | Complete REST API specification with request/response schemas. |
| [**DATABASE_SCHEMA.md**](DATABASE_SCHEMA.md) | Relational schema, DDL statements, and entity-relationship diagram. |
| [**TESTING.md**](TESTING.md) | Comprehensive test suite overview, test matrix, and verification logs. |
| [**DEMO_GUIDE.md**](DEMO_GUIDE.md) | Minute-by-minute 15-minute presentation script for faculty demonstration. |
| [**FACULTY_QA.md**](FACULTY_QA.md) | In-depth technical answers to 19 challenging faculty evaluation questions. |

---

## Decision-Support Disclaimer
RISKORA is an institutional decision-support system. It generates probabilistic risk signals and quantitative recommendations to assist qualified credit underwriters. Final lending authority, policy compliance, and loan disbursal decisions remain the sole responsibility of authorized human underwriters.

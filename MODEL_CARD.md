# RISKORA Model Card: Calibrated HistGradientBoosting Risk Model v1.0

---

## 1. Model Details

- **Model Name**: RISKORA Calibrated Micro-Lending Default Classifier
- **Model Version**: `riskora-ml-v1.0`
- **Developed By**: RISKORA Engineering & Data Science Team
- **Model Date**: September 2026
- **Model Type**: Supervised Binary Classifier (Histogram-based Gradient Boosted Decision Trees + CalibratedClassifierCV)
- **Framework**: `scikit-learn` 1.9.1, Python 3.12, Joblib serialization
- **License**: Proprietary Academic & Enterprise Use
- **Contact**: risk-engineering@riskora.local

---

## 2. Intended Use

### Primary Intended Uses
- **Credit Underwriting Decision Support**: Providing calibrated probability of default (PD) estimates and feature attributions for digital micro-lending loan requests (₹25,000 to ₹10,00,000).
- **Syndicated Funding Structuring**: Guiding capital syndication decisions (Single-Lender vs. Fractional Multi-Lender) based on applicant default risk.
- **Portfolio Risk Monitoring**: Segmenting loan portfolios into Low, Medium, and High credit risk bands for liquidity planning and provisioning.

### Out-of-Scope & Prohibited Uses
- **Autonomous Credit Denial**: The model MUST NOT be used for automated, unappealable adverse credit actions without human underwriter review.
- **Unsecured Mega-Loans**: Not calibrated for corporate, commercial, or large-ticket real estate loans (> ₹50,00,000).
- **Discriminatory Underwriting**: The model MUST NOT ingest prohibited demographic variables (religion, caste, sexual orientation, disability status).

---

## 3. Training & Benchmark Data

- **Dataset**: Historical Micro-Lending Default Benchmark Dataset (`data/loan_default_full.csv`).
- **Dataset Size**: 12,000 loan records across 18 borrower and loan contract features.
- **Class Balance**: 1,330 defaults (11.08% empirical default rate), 10,670 non-defaults.
- **Partitioning**: Stratified split — 70% Train (8,400), 15% Validation (1,800), 15% Held-Out Test (1,800).
- **Target Variable**: `Default` ($1 =$ default, $0 =$ performing). Target leakage strictly prevented by excluding `Default` from feature transformers.

---

## 4. Quantitative Evaluation Metrics

Performance evaluated on **held-out test set (1,800 unseen records)**:

| Metric | Measured Value | Standard Benchmark | Interpretation |
|---|:---:|:---:|---|
| **ROC-AUC** | **0.7919** | $> 0.75$ | Strong overall discriminatory ability across all thresholds |
| **PR-AUC** | **0.4023** | $> 0.25$ (Base: 0.11) | High precision-recall concentration in imbalanced default detection |
| **Brier Score** | **0.0821** | $< 0.12$ | Outstanding probabilistic calibration accuracy |
| **Test Precision @ 0.20** | **36.2%** | $> 30.0\%$ | High-risk pool captures high proportion of true defaults |
| **Test Recall @ 0.20** | **40.2%** | $> 35.0\%$ | Substantial capture of potential loss events |

### Risk Band Performance

| Risk Band | Predicted Probability | Test Population | Observed Default Rate |
|---|:---:|:---:|:---:|
| **LOW** | $< 8.0\%$ | 960 (53.3%) | **3.75%** |
| **MEDIUM** | $8.0\% – 19.9\%$ | 619 (34.4%) | **13.41%** |
| **HIGH** | $\ge 20.0\%$ | 221 (12.3%) | **36.20%** |

---

## 5. Ethical Considerations & Fairness

- **Demographic Parity**: Educational attainment and marital status are included only for cash-flow stability context. The model relies primarily on objective financial behavior (Credit Score, DTI, Loan-to-Income, Employment Tenure).
- **Explainability**: Every inference is accompanied by local feature attribution identifying specific upward pressure drivers and protective mitigators.
- **Decision-Support Boundary**: Clear disclosures inform underwriters that attributions represent statistical correlations from empirical data, preserving human accountability.

---

## 6. Limitations & Caveats

1. **Macroeconomic Shocks**: Model trained on normalized credit cycles. Extreme macroeconomic shocks (e.g. pandemics, sudden interest rate spikes) may cause distribution shift.
2. **Thin-File Applicants**: Applicants with fewer than 12 months of credit bureau history receive lower data quality ratings and are routed for enhanced human verification.
3. **Model Retraining Schedule**: Quarterly monitoring for Population Stability Index (PSI) and Concept Drift is recommended.

# RISKORA — Quality Assurance & Testing Suite

---

## 1. Test Architecture & Coverage

RISKORA features a comprehensive automated testing suite structured across unit, domain, and API integration boundaries.

```
tests/
├── test_riskora.py          # Domain & unit test suite (12 tests)
└── test_api_integration.py # Tornado asynchronous REST API integration suite (9 tests)
```

Total Automated Tests: **21 passing tests (100% success rate)**.

---

## 2. Test Execution Commands

From the project root directory (`RISKORA_V1_0_Updated`):

### Run All Automated Tests
```powershell
python -m unittest discover tests
```

### Run Domain & Unit Tests Only
```powershell
python -m unittest tests/test_riskora.py
```

### Run API Integration Tests Only
```powershell
python -m unittest tests/test_api_integration.py
```

---

## 3. Test Coverage Matrix

| Test Module | Test Case | Target Component | Verification Objective | Result |
|---|---|---|---|:---:|
| `test_riskora.py` | `test_high_risk_inference` | `ml.infer.RiskInferenceEngine` | Validates that high-hazard applicant produces $PD \ge 0.20$, Risk Level `HIGH`, and top upward drivers. | **PASS** |
| `test_riskora.py` | `test_low_risk_inference` | `ml.infer.RiskInferenceEngine` | Validates that prime applicant produces $PD < 0.08$, Risk Level `LOW`, and protective mitigators. | **PASS** |
| `test_riskora.py` | `test_complete_profile` | `backend.services.data_quality` | Asserts complete documentation achieves score $\ge 85$ and `EXCELLENT` tier. | **PASS** |
| `test_riskora.py` | `test_missing_and_contradictory` | `backend.services.data_quality` | Asserts missing income and impossible tenure (10y tenure @ age 20) triggers contradiction flags. | **PASS** |
| `test_riskora.py` | `test_normal_profile` | `backend.services.anomaly_detector` | Asserts standard borrower profile produces zero anomaly flags and `NORMAL` status. | **PASS** |
| `test_riskora.py` | `test_extreme_leverage_anomaly` | `backend.services.anomaly_detector` | Asserts $3.3\times$ debt overhang triggers `EXTREME_LEVERAGE_ANOMALY`. | **PASS** |
| `test_riskora.py` | `test_single_lender_funding` | `backend.services.funding_service` | Confirms sole lender receives $100\%$ share and Herfindahl Index (HHI) equals $10,000$. | **PASS** |
| `test_riskora.py` | `test_fractional_funding` | `backend.services.funding_service` | Confirms syndication across $3$ lenders sums to exactly $100.0\%$ and exact loan amount. | **PASS** |
| `test_riskora.py` | `test_amortisation_zero_balance`| `backend.services.repayment_service` | Validates annuity formula, principal/interest split, and exact final payment balance to $₹0.00$. | **PASS** |
| `test_riskora.py` | `test_bi_monthly_schedule` | `backend.services.repayment_service` | Validates 24-period annual frequency ($6$ months $= 12$ installments). | **PASS** |
| `test_riskora.py` | `test_waterfall_allocation` | `backend.services.repayment_service` | Verifies Largest Contribution First (LCF) waterfall reconciles $100\%$ of payments without loss. | **PASS** |
| `test_riskora.py` | `test_seed_cases_exist` | `backend.database` | Verifies SQLite tables and 6 core seed cases (Rahul P, Arun Kumar, etc.) populate on boot. | **PASS** |
| `test_api_integration.py` | `test_health_endpoint` | `/api/health` | Verifies `200 OK` and `OPERATIONAL` status. | **PASS** |
| `test_api_integration.py` | `test_loans_list` | `/api/loans` | Verifies loan request queue returns seeded records with borrower joins. | **PASS** |
| `test_api_integration.py` | `test_loan_detail` | `/api/loans/LR-1054` | Verifies single loan retrieval with assessment, funding, and repayment state. | **PASS** |
| `test_api_integration.py` | `test_risk_analysis_endpoint`| `/api/risk/analyze` | Verifies end-to-end ML inference, drivers, data quality, and anomaly payload. | **PASS** |
| `test_api_integration.py` | `test_scenario_simulate` | `/api/risk/simulate` | Verifies What-If sensitivity recalculation and comparison deltas. | **PASS** |
| `test_api_integration.py` | `test_funding_optimize` | `/api/funding/optimize` | Verifies syndication calculation and HHI computation. | **PASS** |
| `test_api_integration.py` | `test_repayment_generate` | `/api/repayment/generate` | Verifies amortisation schedule generation. | **PASS** |
| `test_api_integration.py` | `test_dataset_explorer` | `/api/dataset/explorer` | Verifies server-side pagination, summary stats, and target isolation. | **PASS** |
| `test_api_integration.py` | `test_model_metrics` | `/api/model/metrics` | Verifies live test set ROC-AUC, PR-AUC, confusion matrix, and feature weights. | **PASS** |

---

## 4. Test Verification Output
```text
----------------------------------------------------------------------
Ran 21 tests in 4.667s

OK
```
All critical calculations, ML predictions, and API contracts are fully validated.

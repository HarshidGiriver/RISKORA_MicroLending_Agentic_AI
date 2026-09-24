# RISKORA — REST API Documentation
**Institutional API Gateway Specification**

Base URL: `http://localhost:8000`  
Protocol: HTTP/1.1 REST  
Content-Type: `application/json`

---

## 1. System & Authentication Endpoints

### `GET /api/health`
Checks operational health of API gateway, ML engine, and database.
- **Response `200 OK`**:
```json
{
  "status": "OPERATIONAL",
  "service": "RISKORA AI/ML Micro-Lending Risk Platform",
  "version": "1.0.0",
  "ml_engine": "Calibrated HistGradientBoosting v1.0",
  "database": "SQLite Persistent Relational Storage"
}
```

---

### `POST /api/auth/login`
Authenticates reviewer and records underwriting session.
- **Request Body**:
```json
{
  "name": "Dr. Sarah Reviewer"
}
```
- **Response `200 OK`**:
```json
{
  "success": true,
  "user": {
    "id": "USR-1042",
    "name": "Dr. Sarah Reviewer",
    "role": "CHIEF_RISK_ANALYST",
    "session_active": true
  }
}
```

---

## 2. Loan Management Endpoints

### `GET /api/loans`
Retrieves loan request queue with search and status filtering.
- **Query Parameters**:
  - `search` (optional): Query string matching ID, borrower, amount, or purpose.
  - `filter` (optional): `all`, `high` (high risk only), `analyzed`, `incomplete`.
- **Response `200 OK`**:
```json
{
  "count": 6,
  "loans": [
    {
      "id": "LR-1054",
      "borrower_name": "Rahul P",
      "loan_amount": 120000,
      "credit_score": 548,
      "dti_ratio": 0.52,
      "risk_score": 70,
      "risk_level": "HIGH",
      "status": "REQUEST_RECEIVED"
    }
  ]
}
```

---

### `GET /api/loans/{id}`
Returns complete underwriting dossier for a single loan, including borrower demographics, latest risk assessment, committed funding structure, and repayment schedule.
- **Response `200 OK`**:
```json
{
  "id": "LR-1054",
  "borrower_name": "Rahul P",
  "loan_amount": 120000,
  "credit_score": 548,
  "dti_ratio": 0.52,
  "income": 280000,
  "assessment": { ... },
  "funding": { ... },
  "repayment": { ... }
}
```

---

## 3. Risk Intelligence & Simulation Endpoints

### `POST /api/risk/analyze`
Executes real-time calibrated ML inference, feature attribution, data quality scoring, and anomaly detection.
- **Request Body**:
```json
{
  "loanId": "LR-1054",
  "Income": 280000,
  "LoanAmount": 120000,
  "CreditScore": 548,
  "DTIRatio": 0.52,
  "MonthsEmployed": 8,
  "NumCreditLines": 9,
  "EmploymentType": "Contract",
  "HasCoSigner": "No"
}
```
- **Response `200 OK`**:
```json
{
  "loan_id": "LR-1054",
  "probability_of_default": 0.3073,
  "probability_pct": 30.73,
  "risk_score": 70,
  "risk_level": "HIGH",
  "review_level": "ENHANCED_UNDERWRITING",
  "recommended_action": "Escalate to Senior Underwriter. Require fractional funding structure...",
  "risk_drivers": [
    {
      "factor": "Subprime Credit Score",
      "impact_pts": 24,
      "description": "Credit score of 548 is substantially below prime thresholds...",
      "feature": "CreditScore",
      "val": 548.0
    }
  ],
  "protective_factors": [],
  "data_quality": {
    "data_quality_score": 92,
    "quality_tier": "EXCELLENT",
    "completeness_pct": 93.3,
    "missing_required_fields": []
  },
  "anomaly_indicators": {
    "anomaly_detected": false,
    "anomaly_score": 0.12,
    "anomaly_level": "NORMAL",
    "indicators": []
  },
  "model_metadata": {
    "version": "riskora-ml-v1.0",
    "algorithm": "HistGradientBoosting + CalibratedClassifierCV (Sigmoid)"
  }
}
```

---

### `POST /api/risk/simulate`
Executes real-time What-If sensitivity simulation on modified candidate values without altering saved loan files.
- **Request Body**:
```json
{
  "baseLoanId": "LR-1054",
  "scenario": {
    "LoanAmount": 90000,
    "CreditScore": 640,
    "DTIRatio": 0.35
  }
}
```
- **Response `200 OK`**:
```json
{
  "base": { "score": 70, "pd_pct": 30.73, "level": "HIGH" },
  "scenario": {
    "score": 48,
    "pd_pct": 14.2,
    "level": "MEDIUM",
    "indicative_emi": 2989.5,
    "recommended_mode": "fractional"
  },
  "comparison": {
    "score_delta": -22,
    "pd_delta_pts": -16.53,
    "direction": "DECREASED_RISK"
  }
}
```

---

## 4. Syndicated Funding & Waterfall Repayment Endpoints

### `POST /api/funding/optimize`
Calculates single-lender or syndicated fractional capital commitments and computes Herfindahl-Hirschman Index (HHI) concentration metrics.
- **Request Body**:
```json
{
  "loanId": "LR-1054",
  "amount": 120000,
  "riskLevel": "HIGH",
  "mode": "fractional",
  "lenderCount": 3
}
```
- **Response `200 OK`**:
```json
{
  "mode": "fractional",
  "total_requested": 120000,
  "herfindahl_index": 3584.2,
  "largest_lender_share": 44.8,
  "concentration_rating": "MODERATE_CONCENTRATION",
  "positions": [
    { "lender_id": "LND-101", "lender_name": "Apex Micro-Credit Fund", "share_pct": 44.8, "committed_amount": 53760.0, "is_lead": true },
    { "lender_id": "LND-102", "lender_name": "Beacon Capital Partners", "share_pct": 32.8, "committed_amount": 39360.0, "is_lead": false },
    { "lender_id": "LND-103", "lender_name": "Crestline Lending Syndicate", "share_pct": 22.4, "committed_amount": 26880.0, "is_lead": false }
  ]
}
```

---

### `POST /api/repayment/generate`
Generates full amortisation schedule and applies multi-lender waterfall allocations.
- **Request Body**:
```json
{
  "loanId": "LR-1054",
  "principal": 120000,
  "rate": 12.5,
  "term": 36,
  "scheduleType": "monthly",
  "allocationPolicy": "pro-rata",
  "positions": [ ... ]
}
```
- **Response `200 OK`**:
```json
{
  "schedule_type": "monthly",
  "allocation_policy": "pro-rata",
  "indicative_emi": 4014.28,
  "total_interest": 24514.08,
  "total_repayable": 144514.08,
  "installments": [ ... ],
  "lender_summary": [ ... ]
}
```

---

### `POST /api/repayment/record`
Records payment receipt against an installment and updates persistent ledger.
- **Request Body**:
```json
{
  "loanId": "LR-1054",
  "installmentNum": 1,
  "amount": 4014.28
}
```
- **Response `200 OK`**:
```json
{
  "success": true,
  "message": "Installment #1 recorded as PAID."
}
```

---

## 5. Dataset Explorer & Model Metrics

### `GET /api/dataset/explorer`
Server-side paginated dataset records with search, risk filters, and ground truth default outcomes.
- **Query Parameters**: `page`, `limit`, `search`, `risk`, `sort`.
- **Response `200 OK`**:
```json
{
  "pagination": { "page": 1, "limit": 20, "total_records": 12000, "total_pages": 600 },
  "summary_stats": {
    "dataset_size": 12000,
    "historical_default_rate": 11.08,
    "avg_credit_score": 645.2,
    "avg_loan_amount": 124500.0,
    "target_isolated": true
  },
  "rows": [ ... ]
}
```

---

### `GET /api/model/metrics`
Returns test set validation metrics, confusion matrix, and feature importances.
- **Response `200 OK`**:
```json
{
  "test_metrics": {
    "roc_auc": 0.7919,
    "pr_auc": 0.4023,
    "brier_score": 0.0821,
    "precision": 0.362,
    "recall": 0.402,
    "confusion_matrix": {
      "true_negative": 1460,
      "false_positive": 141,
      "false_negative": 119,
      "true_positive": 80
    }
  },
  "risk_bands": {
    "Low": { "count": 960, "defaults": 36, "empirical_default_rate": 3.75 },
    "Medium": { "count": 619, "defaults": 83, "empirical_default_rate": 13.41 },
    "High": { "count": 221, "defaults": 80, "empirical_default_rate": 36.2 }
  }
}
```

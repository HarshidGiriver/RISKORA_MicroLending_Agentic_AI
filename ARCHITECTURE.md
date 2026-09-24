# RISKORA — System Architecture Specification
**AI-Assisted Risk-Based Framework for a Digital Micro-Lending Platform**

---

## 1. Overall System Architecture

The RISKORA platform is structured as an institutional three-tier financial workstation comprising an asynchronous REST API Gateway, modular core computational services, an embedded relational data layer, and an explainable machine learning inference engine.

```mermaid
flowchart TD
    subgraph ClientTier["Institutional Client Workstation (HTML5 / ES6+ / CSS3)"]
        UI_Gate["Access Gate & Identity Reveal"]
        UI_Cmd["Command Center & Active Workflow"]
        UI_Queue["Loan Request Queue & Filters"]
        UI_Risk["Risk Intelligence & SHAP Attribution"]
        UI_Sim["Scenario Lab (What-If ML Simulation)"]
        UI_Fund["Syndicated Funding Optimizer"]
        UI_Repay["Amortisation & Waterfall Repayment"]
        UI_Exp["Lender Portfolio Exposure Monitor"]
        UI_Report["Auditable Decision Dossier (Print/PDF)"]
        UI_Data["Dataset Explorer & Target Validation"]
        UI_Val["Model Validation & Confusion Matrix"]
        UI_Sand["What-If Candidate Sandbox"]
    end

    subgraph APITier["REST API Gateway & Controllers (Python / Tornado 6.5)"]
        API_Auth["/api/auth/login"]
        API_Loans["/api/loans [GET, POST, :id]"]
        API_Risk["/api/risk/analyze & /simulate"]
        API_Fund["/api/funding/optimize"]
        API_Repay["/api/repayment/generate & /record"]
        API_Exp["/api/exposure/portfolio"]
        API_Data["/api/dataset/explorer"]
        API_Metrics["/api/model/metrics"]
    end

    subgraph LogicTier["Core Analytical & Underwriting Engines"]
        ML_Engine["ML Engine: Calibrated HistGradientBoosting + Sigmoid Scaling"]
        DQ_Engine["Data Quality Engine: Completeness, Validity, Consistency"]
        Anom_Engine["Anomaly Engine: Multivariate Outliers & Patterns"]
        Synd_Engine["Funding Service: HHI Concentration & Syndication"]
        Waterfall_Engine["Repayment Service: Multi-frequency & Waterfall Allocations"]
    end

    subgraph DataTier["Persistence & Artifact Registry"]
        DB[(SQLite: riskora.db)]
        Artifacts[("Model Registry: riskora_model.joblib, preprocessor.joblib, model_metrics.json")]
        CSV_Data[("Benchmark Data: loan_default_full.csv (12,000 records)")]
    end

    ClientTier <-->|Asynchronous JSON / HTTP REST| APITier
    API_Risk --> ML_Engine
    API_Risk --> DQ_Engine
    API_Risk --> Anom_Engine
    API_Fund --> Synd_Engine
    API_Repay --> Waterfall_Engine
    API_Loans --> DB
    API_Repay --> DB
    API_Fund --> DB
    API_Risk --> DB
    API_Data --> CSV_Data
    API_Metrics --> Artifacts
    ML_Engine --> Artifacts
```

---

## 2. Machine Learning Training & Evaluation Pipeline

The ML pipeline operates under strict data-leakage controls: the target variable `Default` is strictly isolated, and transformers are fitted exclusively on the stratified training split.

```mermaid
flowchart TD
    D1["Raw Benchmark Dataset (12,000 Records, 18 Columns)"] --> D2["Target Isolation: y = Default (0 / 1)"]
    D2 --> D3["Feature Matrix X (17 Raw Attributes)"]
    D3 --> D4["Feature Engineering: LoanToIncome, MonthlyBurdenRatio"]
    D4 --> D5["Stratified Split (70% Train: 8,400 | 15% Val: 1,800 | 15% Test: 1,800)"]
    
    subgraph Preprocessing["Preprocessing Pipeline (Fit on Train Only)"]
        P_Num["Numeric Transformer: StandardScaler (11 Features)"]
        P_Cat["Categorical Transformer: OneHotEncoder (7 Features)"]
    end
    D5 --> Preprocessing
    
    subgraph Benchmarking["Candidate Model Benchmarking (Validation Set)"]
        M1["Logistic Regression (L2 Regularized)"]
        M2["Random Forest (120 Trees, Balanced Weights)"]
        M3["HistGradientBoosting (Champion: AUC 0.799, Brier 0.081)"]
    end
    Preprocessing --> Benchmarking

    Benchmarking --> M_Select["Champion Selection: HistGradientBoosting"]
    M_Select --> M_Calib["Probability Calibration: CalibratedClassifierCV (Sigmoid / Platt, 5-Fold CV)"]
    M_Calib --> M_Eval["Unseen Test Set Evaluation (1,800 Records)"]
    
    subgraph EvaluationMetrics["Test Performance Verification"]
        E1["ROC-AUC: 0.7919"]
        E2["PR-AUC: 0.4023"]
        E3["Brier Score: 0.0821"]
        E4["Confusion Matrix @ 0.20 Threshold (TN: 1460, FP: 141, FN: 119, TP: 80)"]
        E5["Risk Band Monotonicity: Low (3.75%), Med (13.41%), High (36.20%)"]
    end
    M_Eval --> EvaluationMetrics
    EvaluationMetrics --> Export["Export Artifacts: riskora_model.joblib, preprocessor.joblib, model_metrics.json"]
```

---

## 3. Risk Assessment Execution Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Underwriter as Credit Underwriter
    participant UI as Risk Workstation UI
    participant Server as REST API Gateway
    participant DQ as Data Quality Engine
    participant Anom as Anomaly Detector
    participant ML as ML Inference Engine
    participant DB as SQLite Persistence

    Underwriter->>UI: Click "Run / Refresh ML Analysis"
    UI->>Server: POST /api/risk/analyze {loanId: "LR-1054", attributes...}
    
    Server->>DQ: evaluate(attributes)
    DQ-->>Server: {data_quality_score: 92, completeness_pct: 93, warnings: []}
    
    Server->>Anom: evaluate(attributes)
    Anom-->>Server: {anomaly_detected: false, anomaly_score: 0.08, indicators: []}
    
    Server->>ML: predict(attributes)
    Note over ML: Normalize -> Transform -> Predict Proba -> Platt Calibration -> Tree Attribution
    ML-->>Server: {probability_of_default: 0.3073, risk_score: 70, risk_level: "HIGH", drivers: [...], protective: [...]}
    
    Server->>DB: INSERT INTO risk_assessments & UPDATE loans (status='RISK_ASSESSED')
    DB-->>Server: Transaction Committed
    
    Server-->>UI: Unified Intelligence Payload (Score, PD, Drivers, DQ, Anomaly)
    UI->>Underwriter: Renders Gauge Ring, Risk Drivers (+pts), Protective (-pts), DQ Audit, Anomaly Badge
```

---

## 4. Dataset Ingestion & Target Isolation Flow

```mermaid
flowchart LR
    CSV["Uploaded or Bundled CSV"] --> Ingest["Ingestion Layer: Column Mapping & Alias Detection"]
    Ingest --> LeakageCheck{"Contains Ground Truth 'Default'?"}
    
    LeakageCheck -- Yes --> Isolate["Strict Isolation: Ground Truth retained ONLY for post-hoc validation"]
    LeakageCheck -- No --> FeaturesOnly["Production Feature Vector"]
    
    Isolate --> FeatureVector["Input Matrix X (Default Excluded)"]
    FeaturesOnly --> FeatureVector
    
    FeatureVector --> ML_Inf["ML Inference Engine"]
    ML_Inf --> Pred["Calibrated Risk Score & Default Probability"]
    
    Pred --> Compare["Post-Analysis Confusion Matrix & Risk-Band Default Rate Separation"]
    Isolate -.->|Ground Truth Validation| Compare
```

---

## 5. Funding Structure & Syndication Architecture

```mermaid
flowchart TD
    subgraph Input["Underwriting Trigger"]
        LoanReq["Active Loan Request (Principal P, Risk Level R)"]
    end

    subgraph DecisionNode{"Syndication Logic"}
        LoanReq --> Mode{"Mode Selection"}
        Mode -->|Single Lender| Single["100% Capital Committed by Sole Lender"]
        Mode -->|Fractional Syndication| Fract["Syndication Across K Lenders (K in 2..6)"]
    end

    subgraph ConcentrationAnalytics["Lender Concentration & HHI Engine"]
        Single --> HHI_High["HHI = 10,000 (Maximum Counterparty Concentration)"]
        Fract --> HHI_Calc["Calculate HHI = Sum(s_i^2)"]
        HHI_Calc --> HHI_Grade{"HHI Evaluation"}
        HHI_Grade -->|< 2,500| Dist["Well-Distributed Syndication"]
        HHI_Grade -->|2,500 - 5,000| Mod["Moderate Concentration"]
        HHI_Grade -->|> 5,000| High["High Lead Concentration"]
    end

    subgraph CapitalAllocation["Exact Capital Commitment"]
        Fract --> Shares["Share Allocation: Lead ~40%, Participant B ~35%, Participant C ~25%"]
        Shares --> ExactPennies["Exact Paise Reconciliation: Sum(Amounts) == Loan Principal"]
    end
```

---

## 6. Repayment Engine Flow & Schedule Generation

```mermaid
flowchart TD
    Params["Principal P, Rate r, Term N, Schedule Type"] --> AnnuityFormula["Annuity Formula: EMI = P * [r(1+r)^N] / [(1+r)^N - 1]"]
    
    AnnuityFormula --> FreqRouter{"Schedule Frequency"}
    FreqRouter -->|Monthly| M_Sched["Monthly Intervals (e.g. 5th of each month)"]
    FreqRouter -->|Bi-Monthly| BM_Sched["Bi-Monthly Intervals (5th & 20th, r = rate/24, N = term*2)"]
    FreqRouter -->|Flexible| Flex_Sched["Flexible Due Window (1st–7th of month with grace period)"]

    M_Sched --> Loop["Installment Generation Loop (i = 1 .. N)"]
    BM_Sched --> Loop
    Flex_Sched --> Loop

    Loop --> Split["Calculate Periodic Interest: Balance * periodic_rate"]
    Split --> Prin["Calculate Principal Component: EMI - Interest"]
    Prin --> Bal["Update Remaining Balance: Balance - Principal"]
    Bal --> PennyCheck{"Last Installment (i == N)?"}
    PennyCheck -- Yes --> ZeroAbsorption["Absorb Rounding Difference: Principal = Balance, Balance = 0.00"]
    PennyCheck -- No --> Next["Next Installment"]
    ZeroAbsorption --> OutputTable["Reconciled Amortisation Ledger"]
```

---

## 7. Repayment Waterfall Allocation Architecture

```mermaid
flowchart TD
    PaymentEvent["Repayment Received: Installment Payment = Principal + Interest"] --> PolicySelector{"Allocation Policy"}
    
    PolicySelector -->|Pro-Rata (Default)| ProRata["Distribute Principal & Interest Proportional to Original Capital Share"]
    PolicySelector -->|Largest Contribution First (LCF)| LCF["Waterfall: Direct Principal to Lender with Highest Outstanding Balance Until Parity"]
    PolicySelector -->|Earliest Funding First (FIFO)| FIFO["Waterfall: Direct Principal in Order of Capital Commitment Timestamp"]
    
    ProRata --> BalanceUpdate["Update Individual Lender Balances & Cumulative Returns"]
    LCF --> BalanceUpdate
    FIFO --> BalanceUpdate
    
    BalanceUpdate --> Reconcile["Reconciliation Check: Sum(Lender Allocations) == Total Installment Received"]
```

---

## 8. AI/ML Deployment Architecture

```mermaid
flowchart LR
    subgraph Runtime["Python Tornado Runtime (Port 8000)"]
        Server["Tornado Application Gateway"]
        InferenceWorker["Preloaded RiskInferenceEngine (In-Memory Model)"]
        DB_Layer["SQLite Connection Pool (riskora.db)"]
    end

    subgraph Storage["Persisted Files"]
        JoblibModel["ml/artifacts/riskora_model.joblib"]
        JoblibPrep["ml/artifacts/preprocessor.joblib"]
        MetricsJSON["ml/artifacts/model_metrics.json"]
        SQLiteFile["data/riskora.db"]
    end

    JoblibModel -->|Pre-loaded at startup| InferenceWorker
    JoblibPrep -->|Pre-loaded at startup| InferenceWorker
    MetricsJSON -->|Served via REST| Server
    SQLiteFile <--> DB_Layer
    Server <--> InferenceWorker
```

---

## 9. Future Evolution & Enterprise Roadmap

```mermaid
flowchart TD
    V1["Current Release: RISKORA v1.0 (Calibrated HistGBM, Syndicated Funding, Waterfall Repayment)"]
    
    subgraph V2["Release v2.0: Bureau & Real-Time Data Integrations"]
        B1["Account Aggregator (AA) Open Banking Financial Ingestion"]
        B2["Credit Bureau API Integration (CIBIL / Experian / Equifax)"]
        B3["KYC & Government Identity Automated Verification"]
    end
    
    subgraph V2_5["Release v2.5: Continuous ML & Drift Monitoring"]
        M1["Automated Concept Drift & Feature Drift Monitoring (PSI / KS Tests)"]
        M2["Model Registry with A/B Testing & Shadow Inference"]
        M3["Automated Retraining Trigger on Ground-Truth Default Matures"]
    end

    subgraph V3["Release v3.0: Institutional Smart Contracts & Payment Rails"]
        P1["Automated Payment Gateway Integration (UPI / NACH e-Mandates)"]
        P2["Escrow Account Syndication & Automated Pro-Rata Disbursal"]
        P3["Regulatory Reporting Engine (RBI Digital Lending Guideline Compliant)"]
    end

    V1 --> V2
    V2 --> V2_5
    V2_5 --> V3
```

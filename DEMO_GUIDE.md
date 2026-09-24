# RISKORA — Academic Presentation & Live Demonstration Guide
**15-Minute Complete Demonstration Script for Faculty Evaluation**

---

## Presentation Timing Summary
1. **00:00 – 02:00 (2 Mins)**: Product Introduction & Problem Context
2. **02:00 – 05:00 (3 Mins)**: End-to-End Borrower Risk Assessment & Explainability Demo
3. **05:00 – 07:00 (2 Mins)**: Benchmark Dataset & Ground Truth Validation Demo
4. **07:00 – 09:00 (2 Mins)**: Syndicated Funding & Lender Concentration (HHI) Demo
5. **09:00 – 11:00 (2 Mins)**: Waterfall Repayment Schedules & Multi-Lender Payouts Demo
6. **11:00 – 12:00 (1 Min)**: Machine Learning Architecture & Calibration Explanation
7. **12:00 – 13:30 (1.5 Mins)**: Future Enterprise Roadmap
8. **13:30 – 15:00 (1.5 Mins)**: Q&A Wrap-Up

---

## Preparation Before Faculty Presentation
1. Open PowerShell in `c:\Users\DELL\Desktop\RISKORA-MAIN\RISKORA_V1_0_Updated`.
2. Start the unified server:
   ```powershell
   python run.py
   ```
3. Open your browser to `http://localhost:8000`.
4. Keep the page on the Access Gate screen.

---

## STEP 1: Product Introduction & Identity (00:00 – 02:00)

### What to Click
- On the access screen, type your name (e.g. `Dr. Reviewer` or your name).
- Click **ENTER WORKSPACE →**.

### What Appears
- The official RISKORA logo reveal video plays with audio.
- The Command Center opens, showing Active Case `LR-1054` (Rahul P, ₹1,20,000 request), the 7-stage connected case journey, and the live queue snapshot.

### What to Say to Faculty
> "Good morning, respected faculty members. Today I am presenting **RISKORA — an AI-Assisted Risk-Based Framework for a Digital Micro-Lending Platform**.
> 
> Micro-lending serves self-employed and contract workers who often lack extensive formal credit histories. Traditional rule-based lending either bluntly rejects these individuals or extends unhedged credit that defaults.
> 
> RISKORA is designed as an institutional credit workstation that addresses this challenge through four pillars:
> 1. **Calibrated Machine Learning Risk Scoring** that predicts an exact probability of default rather than arbitrary points.
> 2. **Local Explainable AI** showing the exact drivers moving the score.
> 3. **Syndicated Funding Structuring** that distributes lender concentration risk across multiple capital providers.
> 4. **Waterfall Repayment Allocations** with mathematically reconciled amortisation schedules.
> 
> As you can see on the Command Center, RISKORA is built around a single, connected underwriting trail — downstream modules consume the verified state of earlier stages."

### Technical Concept Demonstrated
- Secure reviewer session initialization, asynchronous single-page architecture, and connected state management.

---

## STEP 2: Live Borrower Risk Assessment & Explainability (02:00 – 05:00)

### What to Click
- In the topbar or Command Center, click **Continue review →** (or click **03 Risk Intelligence** in the sidebar).
- On the Risk Intelligence screen, click **Run / Refresh ML Analysis**.

### What Appears
- The gauge ring animates to **Score: 70/100 (HIGH RISK)**.
- Calibrated Default Probability displays **30.73%**.
- **Primary Risk Drivers**:
  - *Subprime Credit Score* (+24 pts): Score of 548 is below prime threshold.
  - *High Debt-to-Income Ratio* (+20 pts): DTI of 52.0%.
  - *Substantial Loan-to-Income Ratio* (+15 pts): Loan amount is 42.9% of income.
  - *Short Employment Tenure* (+9 pts): 8 months in contract role.
  - *Sole Borrower Obligation* (+5 pts): No co-signer.
- **Data Quality Audit**: 92/100 (EXCELLENT) with 14 of 15 fields validated.
- **Anomaly Engine**: Clean profile (no extreme data entry conflicts).
- **Scenario Lab**: Interactive What-If sliders.

### What to Say to Faculty
> "Let us evaluate active borrower Rahul P, who has requested ₹1,20,000 for a small business. When we click 'Run ML Analysis', the request is processed in real time by our trained **HistGradientBoosting model with Sigmoid Platt Calibration**.
> 
> The model returns an estimated **30.73% probability of default**, mapping to an institutional risk score of **70/100**.
> 
> Notice that RISKORA is completely explainable. The underwriter sees exactly why the score is high: subprime credit (+24 pts), a 52% debt-to-income ratio (+20 pts), and short job tenure (+9 pts).
> 
> Furthermore, we have an independent **Data Quality Engine** that audits completeness and validity separately from risk, and an **Anomaly Detector** that scans for contradictory entries.
> 
> If we want to test borrower sensitivity, we can adjust the **Scenario Lab** below. For instance, if the borrower reduces the request to ₹80,000 and adds a co-signer, the default probability immediately drops by 16.5 percentage points."

### Potential Faculty Question
> **Faculty**: *"How do you explain the score? Is this a black box or real explainability?"*
> 
> **Your Answer**: *"We use local tree feature attribution based on gradient path contributions relative to reference training distributions. For every applicant, each feature's marginal contribution is computed in basis points. Crucially, as disclosed on screen, we make a strict distinction between empirical statistical correlation and causal laws — the system serves as decision-support for human underwriters, not an autonomous black box."*

---

## STEP 3: Dataset Explorer & Historical Validation (05:00 – 07:00)

### What to Click
- In the sidebar, click **08 Dataset Explorer**.
- Show the table and summary stats, then click **09 Model Validation**.

### What Appears
- **Dataset Explorer**: 12,000 benchmark loan records with real-time server-side pagination, search, risk filters, and sorting.
- Shows historical default status column (`Default: 0 / 1`).
- **Model Validation Page**:
  - Test ROC-AUC: **0.7919**
  - Test PR-AUC: **0.4023**
  - Test Brier Score: **0.0821**
  - **Confusion Matrix @ 0.20 Cutoff**: TN: 1,460, FP: 141, FN: 119, TP: 80.
  - **Risk Band Default Rate Separation**:
    - Low Risk: **3.75% default rate**
    - Medium Risk: **13.41% default rate**
    - High Risk: **36.20% default rate**

### What to Say to Faculty
> "A core question for any AI lending system is: *Does the risk classification actually separate real-world outcomes?*
> 
> Here in the Dataset Explorer, we have 12,000 historical loan records mirroring the 18-column Coursera/Kaggle loan default schema.
> 
> **Crucially, we enforce strict target leakage prevention**: the `Default` column is isolated and NEVER fed into the feature matrix or inference calculations. It is used exclusively as observed ground truth.
> 
> On our Model Validation screen, we see the empirical outcomes across our held-out test set of 1,800 unseen loans. Look at the default rates:
> - Low-risk loans had an observed default rate of only **3.75%**.
> - Medium-risk loans had **13.41%**.
> - High-risk loans escalated to **36.20%**.
> 
> This monotonic 10× separation demonstrates that our model genuinely distinguishes performing borrowers from default hazards."

### Potential Faculty Question
> **Faculty**: *"Why did you evaluate with PR-AUC and Brier score instead of just accuracy?"*
> 
> **Your Answer**: *"Loan default is an imbalanced classification problem with an ~11% base default rate. A naive model that predicts 'no default' for every loan achieves 89% accuracy but is catastrophic for a lender. PR-AUC measures precision across default recall levels, while the Brier score quantifies whether our predicted 30% probability actually corresponds to a 30% empirical default frequency."*

---

## STEP 4: Syndicated Funding & Lender Concentration (07:00 – 09:00)

### What to Click
- In the sidebar, click **04 Funding Optimizer**.
- Under Funding Mode, select **Fractional Syndication**.
- Select Lender Capacity: **3 Institutional Lenders**.
- Click **Commit Funding Structure →**.

### What Appears
- Interactive capital syndication diagram showing Borrower node receiving ₹1,20,000 from 3 lenders:
  - Lead Lender (Apex Micro-Credit): 44.8% (₹53,760)
  - Lender B (Beacon Capital): 32.8% (₹39,360)
  - Lender C (Crestline Syndicate): 22.4% (₹26,880)
- **Herfindahl-Hirschman Index (HHI)**: 3,584 (Moderate Concentration).
- Prominent banner: *"CRITICAL RISK DISTINCTION: Fractional funding distributes lender concentration risk across participants. It does NOT reduce borrower default probability."*

### What to Say to Faculty
> "Now let us move to capital structuring. For high-risk borrower Rahul P (PD 30.7%), extending ₹1,20,000 from a single lender means that if the borrower defaults, that single lender absorbs a ₹1,20,000 write-off.
> 
> Under RISKORA's **Fractional Syndication Model**, the loan is split across 3 participating institutional lenders. The lead lender takes ₹53,760, while participants take ₹39,360 and ₹26,880.
> 
> We quantify this using the **Herfindahl-Hirschman Index (HHI)** from regulatory economics, which drops from 10,000 under a single lender down to 3,584 under fractional syndication.
> 
> Most importantly, we highlight an essential theoretical distinction: **Fractional funding does not make the borrower safer. It protects institutional lenders from catastrophic single-counterparty exposure**."

### Potential Faculty Question
> **Faculty**: *"Does fractional lending reduce the borrower's default risk?"*
> 
> **Your Answer**: *"No. The borrower's default probability is fundamentally governed by their income, debt obligations, and financial behavior. Fractional funding is a portfolio risk-distribution technique that limits the capital impairment of individual lenders if a default occurs."*

---

## STEP 5: Waterfall Repayment & Payment Execution (09:00 – 11:00)

### What to Click
- In the sidebar, click **05 Repayment Engine**.
- Under Schedule Type, select **Fixed Monthly (e.g. 5th of month)** (or test Bi-Monthly).
- Under Repayment Allocation Policy, select **Largest Contribution First (LCF Waterfall)** (or Pro-Rata).
- Click **Generate Amortisation Plan**.
- Scroll down to the Amortisation table and click **Record Payment** on Installment #1.

### What Appears
- Monthly installment (EMI) calculated at **₹4,014.28** for 36 months @ 12.5% APR.
- Multi-lender reconciliation showing exact principal and interest split.
- Installment table showing Principal, Interest, and Remaining Balance.
- Installment #1 immediately marks as **PAID (green badge)** with verified timestamp and database commit.
- The final installment (#36) balance is exactly **₹0.00**.

### What to Say to Faculty
> "Once funding is structured, RISKORA generates the repayment plan.
> 
> We support multiple institutional frequencies: standard monthly, bi-monthly, and flexible payment windows.
> 
> When repayments arrive, how are they distributed among the 3 syndicate lenders?
> 1. **Pro-Rata Allocation**: Each lender receives payments strictly proportional to their original capital share.
> 2. **Largest Contribution First (Waterfall)**: Priority principal reimbursement is directed to the lender with the highest outstanding exposure until positions equalize, driving down portfolio concentration as quickly as possible.
> 
> In the table, notice our mathematical precision: interest and principal are tracked separately, and the final installment absorbs rounding cents so the closing balance is exactly ₹0.00.
> 
> When I click 'Record Payment' on Installment #1, the payment is registered in our persistent database, and lender balances update live."

---

## STEP 6: Decision Report & Exposure Monitor (11:00 – 13:00)

### What to Click
- Click **06 Exposure Monitor** to see portfolio aggregates.
- Click **07 Decision Report**.
- Show the auditable decision sheet. Click **Print / Save PDF Report**.

### What Appears
- A clean, institutional credit committee decision dossier ready for export.
- Displays Loan ID, Borrower, Score (70/100), Default Probability (30.73%), Model Version (`riskora-ml-v1.0`), Top Drivers, Data Quality rating, Syndicated funding structure, and Underwriting recommendation: **Conditional Approval (Syndicated Funding & Secondary Verification Required)**.
- Browser print dialog opens formatted specifically for institutional PDF output.

### What to Say to Faculty
> "Finally, in the Decision Report, RISKORA synthesizes the entire case history into an auditable credit dossier.
> 
> Every claim on this document has a direct source: the calibrated ML model, the data quality audit, the syndication decision, and the amortisation schedule.
> 
> It provides a clear recommendation: **Conditional Approval**. The loan is not approved under single-lender funding, but is eligible under fractional syndication with secondary income verification.
> 
> The dossier can be saved as an official PDF report for regulatory compliance."

---

## STEP 7: Automated Case Demo & Wrap-Up (13:00 – 15:00)

### What to Click
- Click **Run full case demo** in the topbar.
- Watch the automated sequence walk through the active case smoothly across all screens in real time.

### Closing Statement
> "In conclusion, RISKORA transforms credit underwriting for micro-lending from a subjective or naive rule-based process into a **rigorous, explainable, AI-assisted decision-support platform**.
> 
> All 21 unit and integration tests pass, all predictions are generated by real calibrated models, and our code is fully structured with a modular Python backend and persistent database.
> 
> Thank you, and I am happy to take your questions."

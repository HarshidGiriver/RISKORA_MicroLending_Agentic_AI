# RISKORA — Faculty Defense & Technical Q&A Preparation
**Comprehensive Technical & Mathematical Answers for Academic Review**

---

### Q1: Why use Artificial Intelligence / Machine Learning for micro-lending?
**Answer**:  
"Micro-lending borrowers frequently possess non-linear, non-standard credit profiles (e.g. self-employed or gig workers without traditional salary slips). Traditional credit scoring relies on rigid linear cutoff rules that either reject viable borrowers or fail to recognize subtle, multi-dimensional risk patterns. Machine learning excels at uncovering complex, non-linear interactions across variables—such as how employment tenure modulates debt-to-income tolerance, or how co-signers mitigate loan-to-income pressure. Furthermore, ML models output continuous, calibrated probabilities of default that allow dynamic risk-based pricing and syndicated exposure structuring."

---

### Q2: Why not just use expert heuristic rules?
**Answer**:  
"Heuristic rule systems have three critical limitations in credit underwriting:
1. **Arbitrary Point Weighting**: Rules assign arbitrary additive points (e.g. '+20 points for low credit score') that do not correspond to any statistical probability of loss.
2. **Failure to Model Feature Interactions**: Rules evaluate attributes independently in silos and fail to capture non-linear interactions (e.g., an applicant with a 610 credit score and 5 years of stable business ownership has a very different default profile than an applicant with a 610 score who is unemployed).
3. **Rigid Fragility**: Rule bases become unmaintainable as new attributes are introduced and cannot adapt continuously as macroeconomic environments change."

---

### Q3: Why this specific dataset?
**Answer**:  
"We selected a benchmark dataset mirroring the 18-feature Kaggle/Coursera Loan Default Prediction schema because it is the widely accepted academic and industry benchmark for consumer and micro-lending risk research. It contains a balanced cross-section of applicant demographics (Age, Education, MaritalStatus), financial obligations (DTI, CreditScore, Lines, Mortgage), employment tenure, loan contract terms, and empirical repayment outcomes."

---

### Q4: What is the target variable?
**Answer**:  
"The target variable is `Default`, a binary indicator where:
- $Y = 1$: The borrower experienced a loan default event (unrepaid principal or $>90$ days past due within the loan term).
- $Y = 0$: The borrower successfully serviced and completed repayment of the loan.  
In our 12,000-sample benchmark dataset, there are 1,330 defaults, corresponding to an empirical baseline default rate of **11.08%**."

---

### Q5: How did you prevent data leakage?
**Answer**:  
"We enforced strict architectural safeguards against target leakage:
1. **Target Isolation**: `Default` is strictly separated as supervisory vector $y$ during data ingestion and is completely excluded from feature matrix $X$.
2. **Split-Before-Fit**: The data is split into 70% Train, 15% Validation, and 15% Held-Out Test sets before any transformer fitting. The `StandardScaler` and `OneHotEncoder` are fitted exclusively on the 8,400 training samples.
3. **Inference Purity**: During live inference (`/api/risk/analyze`), the endpoint only accepts loan attributes. The `Default` label is never present in incoming loan applications.
4. **Post-Hoc Verification Only**: In the Dataset Explorer, `Default` is displayed alongside model predictions solely as an observed benchmark to compute empirical confusion matrices and verify risk-band default separation."

---

### Q6: Why did you choose HistGradientBoosting as your champion model?
**Answer**:  
"We evaluated three distinct model architectures:
1. **Logistic Regression (L2)**: Baseline benchmark; produced 0.813 ROC-AUC but a high Brier score loss (0.1687) and struggled with non-linear feature interactions.
2. **Random Forest (120 trees)**: Solid non-linear separation (0.816 ROC-AUC), but probabilities clustered tightly around the base rate, yielding a sub-optimal F1 score (0.2670).
3. **HistGradientBoosting**: Achieved the best probability calibration out-of-the-box with the lowest Brier score loss (**0.0816**), the highest validation F1 score (**0.4169**), and sub-10ms inference time on standard CPUs due to histogram-based numerical feature binning.

Following model selection, we applied **Sigmoid Platt Scaling** via 5-fold cross-validation on the champion model to guarantee calibrated default probabilities."

---

### Q7: Why evaluate using PR-AUC and Brier Score instead of just Accuracy?
**Answer**:  
"1. **Accuracy is Deceptive in Imbalanced Data**: With an 11% baseline default rate, a trivial model that simply predicts 'no default' for 100% of loans achieves 89% accuracy, yet allows every single defaulting borrower to receive a loan, resulting in financial insolvency.
2. **PR-AUC (Precision-Recall Area Under Curve)**: Evaluates the trade-off specifically on the positive minority class (defaults). Our test PR-AUC of **0.4023** is nearly 4× higher than random guessing (0.1108).
3. **Brier Score Loss**:
   $$\text{Brier} = \frac{1}{N} \sum_{i=1}^{N} (p_i - y_i)^2$$
   Measures the mean squared difference between predicted probabilities and actual outcomes. Our test Brier score of **0.0821** verifies that our predicted probabilities function as accurate default probabilities."

---

### Q8: What happens when the dataset is imbalanced?
**Answer**:  
"Loan default datasets are inherently imbalanced (typically 85–92% non-defaults vs. 8–15% defaults). To prevent the model from biasing toward the majority class:
1. We utilized stratified splitting to guarantee identical class proportions across train, validation, and test splits.
2. We benchmarked tree algorithms that split on purity (entropy/histogram gain) rather than raw accuracy.
3. We tuned the decision threshold to $0.20$ based on an asymmetric cost matrix, ensuring that defaults are captured even when predicted probabilities are below 0.50."

---

### Q9: How is Probability of Default different from Risk Score?
**Answer**:  
"1. **Probability of Default (PD)** is a continuous statistical estimate ($\hat{p} \in [0, 1]$) representing the empirical likelihood that a borrower will fail to service their debt obligation.
2. **Risk Score** is an institutional integer index ($0$ to $100$) derived from the calibrated PD using piecewise logistic scaling. It provides an intuitive grading metric for credit committees and operational risk bands:
   - Low Risk: Score $0–30$ ($PD < 8.0\%$)
   - Medium Risk: Score $31–60$ ($8.0\% \le PD < 20.0\%$)
   - High Risk: Score $61–100$ ($PD \ge 20.0\%$)  
The risk score standardizes communication, while the raw PD is used for financial loss calculations, provisioning, and loan pricing."

---

### Q10: How is the score explained to underwriters?
**Answer**:  
"We compute local feature attributions using contrastive tree gradient contributions relative to reference training distributions.
- If a borrower has a credit score of 548, the system reports: `Subprime Credit Score (+24 pts) — Score is substantially below prime threshold (650)`.
- If a borrower has a registered co-signer, the system reports: `Co-Signer Guarantee (-14 pts) — Provides secondary repayment recourse`.

We also include an explicit regulatory disclosure: *Feature attributions indicate empirical statistical correlations from historical data; they are decision-support signals, not deterministic causal laws.*"

---

### Q11: What happens when applicant information is missing?
**Answer**:  
"We decoupled **Data Quality** from **Default Risk**:
1. Missing data does NOT arbitrarily add fake default risk points.
2. Instead, the independent **Data Quality Engine** audits completeness across 8 required and 7 optional fields, assigning a separate **Data Quality Score (0–100%)** and identifying specific missing proofs (e.g. 'Missing Income Proof', 'Unverified Employment Tenure').
3. If critical required fields are missing, the applicant is placed in `CRITICAL_GAPS` tier, and the underwriting recommendation states: *'Complete missing verification before release.'*"

---

### Q12: Can the model detect fraud?
**Answer**:  
"No, and RISKORA explicitly avoids claiming autonomous fraud detection. Detecting fraud requires specialized signals (device fingerprints, IP geolocation, synthetic identity matching, behavioral biometrics).
Instead, RISKORA features an **Anomaly & Irregularity Detector** that flags multivariate statistical outliers—such as an applicant reporting a loan amount $3.5\times$ annual income, an age of 20 with 10 years of continuous employment, or high DTI with zero credit lines.
The system flags this as **'Anomaly Detected — Enhanced Verification Recommended'**. This is an underwriting prompt for manual dossier verification, never an automated fraud accusation."

---

### Q13: Does fractional lending reduce borrower default risk?
**Answer**:  
"**No. This is a vital theoretical distinction in RISKORA**:
- **Borrower Default Risk** is governed by the borrower's income, expenses, debt obligations, and financial behavior. Dividing a loan among 3 lenders does not make the borrower any more capable of repaying.
- **Lender Exposure Concentration** is the percentage of a lender's capital exposed to a single borrower. Fractional syndication distributes that exposure across multiple participants, measured by the Herfindahl-Hirschman Index (HHI).
If a ₹1,20,000 loan defaults under a single lender, that lender loses ₹1,20,000. Under 3-lender fractional syndication, the largest lender's maximum loss is capped at ₹53,760."

---

### Q14: Why do you need repayment allocation policies?
**Answer**:  
"When a loan is funded fractionally by multiple lenders, monthly borrower repayments must be distributed back to participants according to an agreed-upon legal waterfall. Without a defined policy, disputes arise over who receives principal reimbursement first, how prepayments are split, and who absorbs partial payment deficits."

---

### Q15: How is Largest Contribution First (LCF) different from Pro-Rata?
**Answer**:  
"1. **Pro-Rata Allocation**: Every rupee of installment is split strictly proportional to original shares (e.g. Lender A gets 50%, B gets 30%, C gets 20%). Lender exposure remains proportional throughout the life of the loan.
2. **Largest Contribution First (LCF Waterfall)**: All principal repayment is directed with priority to the lender with the highest outstanding balance until balances equalize. This accelerates risk reduction for the lead lender who carried the largest capital risk."

---

### Q16: How will this integrate with real institutional lenders?
**Answer**:  
"In enterprise deployment:
1. Loan requests are ingested via Open Banking Account Aggregators (AA) and bureau APIs (CIBIL/Experian).
2. Institutional lenders connect via secure REST API webhooks or FIX protocols to receive loan syndication offers.
3. Repayments are executed through automated NACH e-mandates / UPI AutoPay rails into an escrow account, where RISKORA's allocation engine dispatches automated split payouts to lender virtual accounts."

---

### Q17: How will the model be retrained over time?
**Answer**:  
"As new loans mature and actual default/repayment outcomes are recorded:
1. Maturing cohorts are appended to the training corpus.
2. The pipeline runs quarterly retraining via `ml/train.py`.
3. Candidate models are benchmarked against the incumbent model on the latest validation split.
4. If a candidate demonstrates superior PR-AUC and lower Brier score without subgroup degradation, it is registered under an incremented version tag (`riskora-ml-v1.1`) in the model registry."

---

### Q18: What happens when the model becomes inaccurate (Concept / Data Drift)?
**Answer**:  
"We monitor two statistical drift metrics:
1. **Population Stability Index (PSI)** on incoming feature distributions:
   $$\text{PSI} = \sum \left( \text{Actual}\% - \text{Expected}\% \right) \times \ln\left(\frac{\text{Actual}\%}{\text{Expected}\%}\right)$$
   A $PSI > 0.25$ indicates significant population drift.
2. **Rolling Brier Score & Default Rate Divergence**: If the observed default rate deviates from predicted PD by more than $20\%$, the system flags a drift alert and falls back to conservative underwriting cutoffs while retraining is triggered."

---

### Q19: What are the primary technical and practical limitations of RISKORA v1.0?
**Answer**:  
"1. **Macroeconomic Stress**: The model does not currently ingest real-time macroeconomic indicators (RBI policy repo rate, CPI inflation).
2. **Alternative Data**: It currently relies on financial and demographic variables; it does not yet incorporate utility bill payments, GST invoices, or telecom data.
3. **Escrow Bank Rails**: While the allocation engine calculates mathematically perfect splits to the penny, physical funds transfer currently relies on integration with payment gateway webhooks (planned for v3.0)."

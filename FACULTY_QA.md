# Faculty questions and answers

These answers describe the current integrated implementation. They distinguish demonstrated behavior from planned work so the presentation does not depend on unsupported claims.

## Purpose and contribution

### What problem does RISKORA address?

It brings borrower intake, risk assessment, human review, funding structure and repayment tracking into one reviewer workflow. The practical contribution is the consistent flow between these steps: the saved borrower profile feeds the model, the decision refers to an assessment, and receipts update exposure from actual allocations.

### Is this a real lending platform?

It is an academic decision-support prototype. The dataset is synthetic, lender positions are simulated and payment recording is an internal ledger event. It does not transfer funds or prove legal eligibility for lending. A real service would need external data validation, operational controls and an appropriate deployment review.

### What changed after the OraAgent integration?

The existing Tornado application gained real local login accounts, roles, borrower create/edit forms, an ORA evidence brief, recorded human decisions and safer partial-payment handling. Useful features were adapted into the existing schema and APIs. The incoming FastAPI backend and alternate model artifacts were not run as a second application.

### Why keep one backend?

The two projects used different schemas, IDs, routes and model contracts. Running both would leave the frontend unsure which loan store and assessment were authoritative. One backend preserves the established shared schema, tested finance logic and saved-case lifecycle.

## Model and data

### Where does the dataset come from?

`ml/generate_data.py` creates 12,000 synthetic rows with seed 42. The labels reflect programmed assumptions and randomness. They are not observed defaults from a bank. The model card and UI identify this source.

### Which algorithm is used and why?

The saved model is HistGradientBoosting calibrated with a sigmoid through five-fold CalibratedClassifierCV. The script also evaluates logistic regression and random forest. HistGradientBoosting has the lowest recorded validation Brier score among those candidates, although random forest has the highest validation ROC AUC. The script explicitly selects the final model; it does not automatically pick a universal winner.

### What are the model inputs?

There are 16 raw fields: nine numeric inputs and seven categorical inputs. Two ratios are derived. Scaling and one-hot encoding produce 26 transformed columns. The data dictionary lists every field, alias, unit, range and fallback. Borrower names and loan IDs are not predictors.

### What does the model score mean?

The primary output is a probability of synthetic default. LOW means below 8%, MEDIUM means 8% to below 20%, and HIGH means at least 20%. The display score is a piecewise transformation bounded to 5–99. It is not a bureau credit score or a probability percentage.

### How well does it perform?

The stored test ROC AUC is 0.7919, average precision is 0.4023 and Brier score is 0.0821. At threshold 0.20, precision is 0.362 and recall is 0.402. Those values apply to 1,800 synthetic test rows. They cannot be claimed as real-world underwriting performance.

### Why not report only accuracy?

The confusion matrix gives 85.56% accuracy, but predicting no defaults for every test row gives 88.94%. The class imbalance makes accuracy a poor standalone claim. The selected threshold misses 119 of 199 synthetic defaults, so recall and the cost of missed defaults matter.

### Are the explanation points SHAP values?

No. They are fixed policy-rule points based on selected inputs. They do not sum to the model prediction and do not quantify causal effects. The global coefficient chart comes from the logistic-regression baseline, not the deployed calibrated tree model. Model-specific explanations are future work.

### Does calibration prove the model is trustworthy?

Calibration is a fitting method, not a guarantee. The Brier score gives one held-out summary on synthetic data. Real-data reliability diagrams, subgroup checks, temporal validation and outcome monitoring remain necessary before a lending deployment.

## ORA and reviewer control

### Is ORA a generative AI agent?

No. The integrated ORA service creates a deterministic summary from saved borrower inputs, the assessment and data-quality findings. It does not call an LLM, search the web or autonomously approve a loan. A future agent should use the same validated APIs and retain human approval for decisions and financial actions.

### What does the evidence digest prove?

It identifies the normalized input snapshot used by the summary. It can help detect that inputs changed. It does not prove the input came from a bank, that a document is genuine or that income is verified.

### How are incomplete applications handled?

Eight inputs are mandatory at creation. Missing Age or categorical fields can be saved as missing, but approval requires all 16 inputs and passing internal consistency checks. Inference fallbacks allow a provisional assessment; they are not written back as factual borrower data.

### Can the model approve a borrower automatically?

No. The reviewer records an explicit decision and note linked to the latest assessment ID. Funding requires approved status and matching saved principal. A low model band or a changed dropdown is insufficient.

### What happens when inputs change?

An unfunded profile can be edited. Its visible assessment eligibility resets and the reviewer must reassess. The old assessment history remains. Funded profiles cannot be edited through this route, and reanalysis does not reset an active repayment stage.

## Funding and accounting

### Does fractional funding reduce borrower default risk?

It spreads one loan across lender positions and changes concentration. It does not change the borrower's probability of default. The same saved assessment is used before and after funding structure changes.

### How do partial payments reconcile?

The service converts monetary values to integer cents, calculates remaining scheduled lender principal and interest buckets and distributes the receipt proportionally with deterministic remainder handling. Every receipt equals the sum of its lender allocations. Cumulative principal receipts, rather than scheduled balances, reduce exposure.

### How are duplicate receipts prevented?

The client supplies an idempotency reference. Repeating the same loan, installment and amount with that reference returns the original receipt. Reusing it for a different event is rejected. The database also has a unique index on new non-NULL references.

### Why are some historical balances unavailable?

Old receipts do not identify their schedule version. Assigning them from installment number alone could misstate balances. The system preserves the records, flags reconciliation and blocks more receipts for those cases. A human-reviewed reconciliation tool has not yet been built.

### Can a schedule change after a payment?

No. A replacement schedule can be generated before receipts, using a new row ID as its version. After a receipt exists, regeneration is blocked so payments keep a stable link to the plan under which they were recorded.

## Security, testing and limits

### How are passwords and sessions protected?

Passwords use random salts and PBKDF2-HMAC-SHA256 with 600,000 iterations. Sessions use random tokens with only their hashes stored in SQLite. Cookies are HttpOnly and SameSite=Strict, expire after eight hours and are revoked on logout. HTTPS still requires deployment configuration; password hashing does not encrypt the whole database.

### How is authorization enforced?

All business APIs require authentication. VIEWER is read-only, REVIEWER can perform case actions and ADMIN can also create accounts. POST requests require a custom header and matching origin when supplied. Static files are allowlisted to keep backend sources, databases and artifacts from being served.

### What testing supports the implementation?

The regression suite exercises input mapping, loan creation, queue filtering, model startup failures, lifecycle guards, authentication, migration preservation, partial/duplicate payments and exact allocations. Tests use isolated temporary databases. A browser walkthrough checked create-to-payment, reload, reports, logout and a 390 by 844 mobile viewport. Manual browser evidence is separate from automated CI coverage.

### What remains before production?

Real-data model validation, deeper end-to-end browser automation, concurrency/load tests, account recovery, secure remote deployment, managed migrations, tested recovery automation and operational monitoring remain. Refunds, write-offs, bank settlement and historical receipt reconciliation also need explicit designs. The project analysis orders this work by correctness and complete workflow before new features.

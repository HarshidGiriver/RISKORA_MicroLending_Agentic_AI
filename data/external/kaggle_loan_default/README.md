# External loan-default dataset

Reviewed and downloaded on 12 October 2026. This folder contains a separately sourced research dataset for RISKORA. The application continues to use `data/loan_default_full.csv` and its existing matching model artifacts.

## Selected source

- Dataset: [Loan Default Prediction Dataset](https://www.kaggle.com/datasets/nikhil1e9/loan-default), `nikhil1e9/loan-default`, version 2.
- Kaggle lists the licence as **CC0: Public Domain**. See [source metadata](https://www.kaggle.com/api/v1/datasets/view/nikhil1e9/loan-default) and [CC0 terms](https://creativecommons.org/publicdomain/zero/1.0/).
- The uploader attributes it to [Coursera's Loan Default Prediction Challenge](https://www.coursera.org/projects/data-science-coding-challenge-loan-default-prediction).
- Local file: `Loan_default.csv`, preserved byte-for-byte without category changes, currency conversion, row filtering or label changes.
- SHA-256: `1d7556a9071e7f9e872dc05a0cad174229fb1164b1cf3470ad35eed195c24278`.

The source describes Default as whether the borrower defaulted, with 1 for default and 0 otherwise. Its feature dictionary identifies Income as annual income and LoanTerm as months. It does not identify the monetary denomination or establish a documented lending cohort, sampling period or default observation horizon. Treat it as an external educational dataset with unverified cohort provenance, not as verified Indian microfinance outcomes. A Kaggle listing and row count alone do not establish real-world suitability.

## Why this source was selected

| Candidate | Fit for this project | Decision |
|---|---|---|
| `nikhil1e9/loan-default` | Default target and all 18 current column names; some category and semantic differences | Downloaded for separate evaluation |
| [Loan Approval Prediction](https://www.kaggle.com/datasets/architsharma01/loan-approval-prediction-dataset) | Target is Approved/Rejected rather than repayment default | Not used as default-risk training data |
| [Credit Risk Dataset](https://www.kaggle.com/datasets/laotse/credit-risk-dataset) | Binary default label, but a different feature set and limited source provenance | Possible future benchmark; not downloaded |
| [Loan Default Dataset](https://www.kaggle.com/datasets/yasserh/loan-default-dataset) | Different fields and limited source provenance | Not selected for the current schema |
| [UCI Default of Credit Card Clients](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients) | Documented Taiwan credit-card repayment cohort; different product, currency and payment-history inputs | Useful independent benchmark, not a direct micro-loan input replacement |

The selected file is the closest structural match among these candidates. This decision does not mean it is the best proven dataset for live lending. None of the reviewed sources establishes an exact match to the intended Indian micro-lending population and current input contract.

## Measured data quality

| Check | Result |
|---|---:|
| Rows | 255,347 |
| Columns | 18 |
| Non-default labels | 225,694 |
| Default labels | 29,653 |
| Default share | 11.61% |
| Empty CSV values | 0 |
| Duplicate complete rows | 0 |
| Duplicate LoanID values | 0 |
| Full-time / Part-time category rows | 127,817 |
| Unemployed with positive MonthsEmployed | 63,292 |
| MonthsEmployed above `(Age - 16) * 12` | 17,274 |

The last two checks apply RISKORA's current consistency rules; they are flags to investigate rather than proof that source records are invalid. For example, a source may mean previous employment tenure instead of current tenure. The source dictionary does not resolve that ambiguity. Counts can overlap and must not be added to estimate the number of affected rows.

`quality_report.json` contains the full numeric ranges, category counts, missingness and application-compatibility findings. It also reports matches to current income-related warning rules. Because currency is unresolved, those warning matches do not establish borrower affordability.

## Input compatibility

All column names match the current training CSV, but matching names are insufficient for deploying a new model.

| Input area | External source | Current application | Required decision |
|---|---|---|---|
| Employment | Full-time, Part-time, Self-employed, Unemployed | Salaried, Contract, Self-employed, Unemployed | Define an evidence-based input contract; Part-time is not equivalent to Contract |
| Income and loan amount | Currency not stated in source dictionary | Annual INR income and INR principal | Confirm source denomination and population before any conversion or deployment |
| Loan term | Months | Months | Unit aligns |
| Target | Default=0/1 | Default=0/1 | Class semantics align, but source default horizon is not documented |
| Employment tenure | Months, with many unemployed/positive-tenure rows | Consistency rule expects zero for unemployed | Resolve current versus historical employment meaning |
| Education and other categories | Current canonical values present | Shared schema values | No category remapping needed for these fields |

Do not relabel Full-time as Salaried or Part-time as Contract automatically. Do not apply an assumed exchange rate or synthesize missing evidence. Do not set `RISKORA_DATA_PATH` to this file while keeping the old artifacts and presenting it as the deployed model's training dataset.

## Reproduce acquisition and audit

From the project root:

```powershell
python scripts/prepare_external_dataset.py
python scripts/prepare_external_dataset.py --check
```

The first command fetches the public version-2 download when the local CSV is absent, reads only the expected member and verifies its exact byte count and SHA-256. It writes the CSV under this directory and creates the quality report. If a local file already exists, it checks that file instead of overwriting it. The second command performs no network request and regenerates the audit of the existing file.

To use an already downloaded archive:

```powershell
python scripts/prepare_external_dataset.py --archive 'path/to/loan-default-v2.zip'
```

The script requires only Python's standard library. It does not load serialized models, import the HTTP application, write SQLite records or alter the runtime configuration. A changed upstream CSV fails its checksum check and requires a separate source review. The downloaded CSV is ignored by Git to keep the repository smaller; the manifest, audit report and retrieval script are maintained in source control.

## Before model adoption

Resolve the input semantics and monetary units, define the target horizon, decide how to handle inconsistent rows and document that decision. Then create a separate train/validation/test experiment with preprocessing fitted only within training folds and keep all candidate artifacts outside `ml/artifacts`. Compare probability calibration, ranking, class-sensitive metrics and subgroup behavior. Results on this source must not be presented as validation of the current INR model or live borrowers.

Only promote a model after its schema, form inputs, feature engineering, explorer labels, model card and regression expectations have been updated together. The current application remains available while this research takes place.

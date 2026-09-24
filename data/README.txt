RISKORA V1.0 DATASET INPUT

Expected file: Loan_default.csv

The application accepts the historical loan-default dataset used for the Review 1 demonstration.
The browser reads the CSV locally; no upload to an external service is required.

Expected core fields:
LoanID, Age, Income, LoanAmount, CreditScore, MonthsEmployed,
NumCreditLines, InterestRate, LoanTerm, DTIRatio, Education,
EmploymentType, MaritalStatus, HasMortgage, HasDependents,
LoanPurpose, HasCoSigner, Default

V1.0 scoring uses borrower and loan attributes only. Default is retained as a historical outcome
for post-analysis validation and is never fed into the risk score.

Source reference:
https://github.com/nderitugichuki/Loan-Default-Prediction

The referenced repository describes a 255,347-row, 18-column Loan_default.csv dataset.

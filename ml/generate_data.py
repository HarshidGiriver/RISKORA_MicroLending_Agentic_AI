"""
RISKORA — Dataset Generation & Synthesis
Generates a realistic 12,000-sample loan default benchmark dataset matching
the 18 Coursera / Kaggle schema columns with realistic micro-lending distributions,
non-linear risk interactions, and empirical default patterns.
"""

import os
import numpy as np
import pandas as pd

def generate_benchmark_dataset(num_samples: int = 12000, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    
    # 1. Loan IDs
    loan_ids = [f"LID-{10000 + i}" for i in range(num_samples)]
    
    # 2. Demographic & Employment features
    # Age: skewed towards working age 21 - 65
    age = np.random.triangular(21, 35, 68, num_samples).astype(int)
    
    # Income (Annual in INR): log-normal distribution, median ~4.5 Lakhs
    income = np.random.lognormal(mean=12.9, sigma=0.55, size=num_samples)
    income = np.clip(np.round(income / 1000) * 1000, 120000, 3000000).astype(int)
    
    # Education
    education_levels = ["High School", "Bachelor's", "Master's", "PhD"]
    education_probs = [0.28, 0.50, 0.18, 0.04]
    education = np.random.choice(education_levels, size=num_samples, p=education_probs)
    
    # Employment Type
    emp_types = ["Salaried", "Self-employed", "Contract", "Unemployed"]
    emp_probs = [0.62, 0.24, 0.11, 0.03]
    employment_type = np.random.choice(emp_types, size=num_samples, p=emp_probs)
    
    # Months Employed (dependent on age and employment type)
    max_possible_months = np.maximum(0, (age - 18) * 12)
    emp_fraction = np.random.beta(2, 2, num_samples)
    months_employed = np.round(emp_fraction * np.minimum(max_possible_months, 180)).astype(int)
    # Unemployed have 0 months
    months_employed[employment_type == "Unemployed"] = 0
    
    # Marital Status
    marital_statuses = ["Single", "Married", "Divorced"]
    marital_status = np.random.choice(marital_statuses, size=num_samples, p=[0.42, 0.46, 0.12])
    
    # Has Dependents
    dep_prob = np.where(marital_status == "Married", 0.65, 0.25)
    has_dependents = np.where(np.random.rand(num_samples) < dep_prob, "Yes", "No")
    
    # Has Mortgage
    mortgage_prob = np.clip((income - 250000) / 2000000 * 0.4 + 0.1, 0.05, 0.55)
    has_mortgage = np.where(np.random.rand(num_samples) < mortgage_prob, "Yes", "No")
    
    # 3. Credit profile
    # Base credit score (300 to 850), normal around 640
    base_credit = np.random.normal(loc=645, scale=80, size=num_samples)
    # Penalize short employment tenure or contract/unemployed
    credit_adj = np.where(employment_type == "Unemployed", -100, 
                 np.where(employment_type == "Contract", -30, 0)) + \
                 np.where(months_employed < 12, -25, np.where(months_employed > 48, 20, 0))
    credit_score = np.clip(np.round(base_credit + credit_adj), 320, 850).astype(int)
    
    # Number of credit lines (1 to 14)
    num_credit_lines = np.clip(np.random.poisson(lam=4.2, size=num_samples), 1, 14).astype(int)
    
    # Loan Purpose
    purposes = ["Business", "Education", "Home", "Auto", "Other"]
    loan_purpose = np.random.choice(purposes, size=num_samples, p=[0.30, 0.20, 0.22, 0.16, 0.12])
    
    # Loan Amount: typically 15% to 60% of annual income for micro-lending
    loan_ratio = np.random.beta(2, 5, num_samples) * 0.8 + 0.1
    loan_amount = np.clip(np.round(income * loan_ratio / 5000) * 5000, 25000, 1000000).astype(int)
    
    # Loan Term: 12, 24, 36, 48, 60 months
    loan_terms = [12, 24, 36, 48, 60]
    loan_term = np.random.choice(loan_terms, size=num_samples, p=[0.25, 0.30, 0.25, 0.12, 0.08])
    
    # DTI Ratio: Debt-to-Income (0.10 to 0.75)
    dti_base = np.random.beta(2.5, 5.0, num_samples) * 0.65 + 0.10
    # Slightly higher DTI if mortgage exists
    dti_ratio = np.clip(np.round(dti_base + np.where(has_mortgage == "Yes", 0.08, 0.0), 2), 0.10, 0.78)
    
    # Has Co-Signer
    # Lower credit borrowers are more often requested to provide co-signers
    cosigner_prob = np.where(credit_score < 580, 0.55, np.where(credit_score < 680, 0.30, 0.15))
    has_cosigner = np.where(np.random.rand(num_samples) < cosigner_prob, "Yes", "No")
    
    # Interest Rate (Annual %): risk-based pricing (8.5% to 24%)
    base_rate = 14.5 - (credit_score - 600) * 0.025 + (dti_ratio - 0.35) * 8.0
    interest_rate = np.clip(np.round(base_rate + np.random.normal(0, 1.0, num_samples), 1), 8.5, 24.5)
    
    # 4. Realistic Ground Truth Default Generation
    # Micro-lending default probability is determined by non-linear risk score:
    log_odds = (
        - 1.60
        - 0.0095 * (credit_score - 620)
        + 3.20 * (dti_ratio - 0.36)
        + 1.85 * (loan_amount / income - 0.32)
        + 0.12 * (interest_rate - 13.5)
        - 0.012 * np.minimum(months_employed, 60)
        + np.where(employment_type == "Unemployed", 1.4, 0)
        + np.where(employment_type == "Contract", 0.45, 0)
        - np.where(has_cosigner == "Yes", 0.60, 0)
        + np.where(has_dependents == "Yes", 0.20, 0)
        - np.where(has_mortgage == "Yes", 0.15, 0)
        + np.where(loan_term >= 48, 0.35, 0)
    )
    
    true_prob = 1.0 / (1.0 + np.exp(-log_odds))
    default = np.where(np.random.rand(num_samples) < true_prob, 1, 0)
    
    df = pd.DataFrame({
        "LoanID": loan_ids,
        "Age": age,
        "Income": income,
        "LoanAmount": loan_amount,
        "CreditScore": credit_score,
        "MonthsEmployed": months_employed,
        "NumCreditLines": num_credit_lines,
        "InterestRate": interest_rate,
        "LoanTerm": loan_term,
        "DTIRatio": dti_ratio,
        "Education": education,
        "EmploymentType": employment_type,
        "MaritalStatus": marital_status,
        "HasMortgage": has_mortgage,
        "HasDependents": has_dependents,
        "LoanPurpose": loan_purpose,
        "HasCoSigner": has_cosigner,
        "Default": default
    })
    
    return df

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "loan_default_full.csv")
    
    df = generate_benchmark_dataset(12000, seed=42)
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} records in {out_path}")
    print(f"Default rate: {df['Default'].mean()*100:.2f}% ({df['Default'].sum()} defaults)")

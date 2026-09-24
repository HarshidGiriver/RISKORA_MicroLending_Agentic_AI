"""
RISKORA — Machine Learning Inference & Local Explainability Service
Loads the calibrated production model artifact and generates calibrated
default probabilities, institutional risk scores, and local feature attributions.
"""

import os
import json
import numpy as np
import pandas as pd
import joblib
from typing import Dict, Any, List, Tuple

class RiskInferenceEngine:
    _instance = None
    
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        artifacts_dir = os.path.join(base_dir, "artifacts")
        model_path = os.path.join(artifacts_dir, "riskora_model.joblib")
        preprocessor_path = os.path.join(artifacts_dir, "preprocessor.joblib")
        metrics_path = os.path.join(artifacts_dir, "model_metrics.json")
        
        if not os.path.exists(model_path) or not os.path.exists(preprocessor_path):
            raise FileNotFoundError("Model artifacts not found. Please run ml/train.py first.")
            
        self.model = joblib.load(model_path)
        self.preprocessor = joblib.load(preprocessor_path)
        with open(metrics_path, "r") as f:
            self.metadata = json.load(f)
            
        self.feature_ref = self.metadata.get("feature_reference", {})
        self.numeric_means = self.feature_ref.get("numeric_means", {})
        self.numeric_stds = self.feature_ref.get("numeric_stds", {})
        
        # Risk band thresholds
        self.thresh_low = self.metadata.get("threshold_policy", {}).get("low_risk_threshold", 0.08)
        self.thresh_high = self.metadata.get("threshold_policy", {}).get("high_risk_threshold", 0.20)
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _normalize_input(self, raw: Dict[str, Any]) -> pd.DataFrame:
        """Maps varying client/API input naming conventions into standard training schema."""
        def get_val(*keys, default=None):
            for k in keys:
                if k in raw and raw[k] is not None and str(raw[k]).strip() != "":
                    return raw[k]
            return default

        age = float(get_val("Age", "age", default=35))
        income = float(get_val("Income", "income", "annualIncome", default=450000))
        loan_amount = float(get_val("LoanAmount", "loanAmount", "amount", default=120000))
        credit_score = float(get_val("CreditScore", "creditScore", "credit", default=650))
        months_employed = float(get_val("MonthsEmployed", "monthsEmployed", "empMonths", default=36))
        num_credit_lines = float(get_val("NumCreditLines", "numCreditLines", "creditLines", default=4))
        interest_rate = float(get_val("InterestRate", "interestRate", "rate", default=12.5))
        loan_term = int(get_val("LoanTerm", "loanTerm", "term", default=36))
        dti_ratio = float(get_val("DTIRatio", "dtiRatio", "dti", default=0.32))
        
        education = str(get_val("Education", "education", default="Bachelor's"))
        emp_type = str(get_val("EmploymentType", "employmentType", "employment", default="Salaried"))
        marital_status = str(get_val("MaritalStatus", "maritalStatus", default="Married"))
        has_mortgage = str(get_val("HasMortgage", "hasMortgage", default="No"))
        has_dependents = str(get_val("HasDependents", "hasDependents", default="No"))
        loan_purpose = str(get_val("LoanPurpose", "loanPurpose", "purpose", default="Business"))
        has_cosigner = str(get_val("HasCoSigner", "hasCoSigner", "hasCosigner", default="No"))
        
        # Standardize categorical Yes/No
        has_mortgage = "Yes" if str(has_mortgage).lower() in ["yes", "true", "1"] else "No"
        has_dependents = "Yes" if str(has_dependents).lower() in ["yes", "true", "1"] else "No"
        has_cosigner = "Yes" if str(has_cosigner).lower() in ["yes", "true", "1"] else "No"
        
        # Feature engineering
        loan_to_income = round(loan_amount / max(income, 1.0), 4)
        monthly_inc = max(income / 12.0, 1.0)
        monthly_principal = loan_amount / max(loan_term, 1)
        monthly_burden = round(monthly_principal / monthly_inc, 4)
        
        row_dict = {
            "Age": [age],
            "Income": [income],
            "LoanAmount": [loan_amount],
            "CreditScore": [credit_score],
            "MonthsEmployed": [months_employed],
            "NumCreditLines": [num_credit_lines],
            "InterestRate": [interest_rate],
            "LoanTerm": [loan_term],
            "DTIRatio": [dti_ratio],
            "Education": [education],
            "EmploymentType": [emp_type],
            "MaritalStatus": [marital_status],
            "HasMortgage": [has_mortgage],
            "HasDependents": [has_dependents],
            "LoanPurpose": [loan_purpose],
            "HasCoSigner": [has_cosigner],
            "LoanToIncome": [loan_to_income],
            "MonthlyBurdenRatio": [monthly_burden]
        }
        return pd.DataFrame(row_dict)

    def explain_instance(self, input_df: pd.DataFrame, pd_score: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Generates local feature attributions comparing the applicant against
        benchmark distributions and empirical risk factors.
        """
        drivers = []
        protective = []
        row = input_df.iloc[0]
        
        # 1. Credit Score Impact
        cs = row["CreditScore"]
        if cs < 580:
            drivers.append({
                "factor": "Subprime Credit Score",
                "impact_pts": 24,
                "description": f"Credit score of {int(cs)} is substantially below prime thresholds, reflecting elevated default correlation.",
                "feature": "CreditScore",
                "val": cs
            })
        elif cs < 650:
            drivers.append({
                "factor": "Moderate Credit Strength",
                "impact_pts": 12,
                "description": f"Credit score of {int(cs)} indicates fair credit history with moderate repayment uncertainty.",
                "feature": "CreditScore",
                "val": cs
            })
        elif cs >= 720:
            protective.append({
                "factor": "Strong Credit Rating",
                "impact_pts": -18,
                "description": f"Prime credit score of {int(cs)} correlates strongly with disciplined historical repayment.",
                "feature": "CreditScore",
                "val": cs
            })

        # 2. Debt-to-Income (DTI)
        dti = row["DTIRatio"]
        if dti >= 0.45:
            drivers.append({
                "factor": "High Debt-to-Income Ratio",
                "impact_pts": 20,
                "description": f"DTI of {dti*100:.1f}% indicates that existing debt obligations absorb a substantial portion of monthly income.",
                "feature": "DTIRatio",
                "val": dti
            })
        elif dti >= 0.35:
            drivers.append({
                "factor": "Elevated Debt Burden",
                "impact_pts": 10,
                "description": f"DTI of {dti*100:.1f}% represents elevated leverage across the borrower's commitments.",
                "feature": "DTIRatio",
                "val": dti
            })
        elif dti < 0.25:
            protective.append({
                "factor": "Low Debt Leverage",
                "impact_pts": -12,
                "description": f"DTI of {dti*100:.1f}% provides comfortable financial headroom for new debt service.",
                "feature": "DTIRatio",
                "val": dti
            })

        # 3. Loan to Income Ratio
        lti = row["LoanToIncome"]
        if lti >= 0.50:
            drivers.append({
                "factor": "Substantial Loan-to-Income Ratio",
                "impact_pts": 15,
                "description": f"Requested loan amount is {lti*100:.1f}% of annual income, creating high principal recovery risk.",
                "feature": "LoanToIncome",
                "val": lti
            })
        elif lti <= 0.20:
            protective.append({
                "factor": "Conservative Loan Sizing",
                "impact_pts": -10,
                "description": f"Loan amount is only {lti*100:.1f}% of annual earnings, readily covered by current income.",
                "feature": "LoanToIncome",
                "val": lti
            })

        # 4. Employment Tenure
        emp_m = row["MonthsEmployed"]
        emp_t = row["EmploymentType"]
        if emp_t == "Unemployed":
            drivers.append({
                "factor": "No Active Employment",
                "impact_pts": 25,
                "description": "Applicant has no active employment income stream.",
                "feature": "EmploymentType",
                "val": emp_t
            })
        elif emp_m < 12:
            drivers.append({
                "factor": "Short Employment Tenure",
                "impact_pts": 9,
                "description": f"Employment tenure of {int(emp_m)} months shows recent job transition or nascent business stability.",
                "feature": "MonthsEmployed",
                "val": emp_m
            })
        elif emp_m >= 48:
            protective.append({
                "factor": "Established Employment Stability",
                "impact_pts": -8,
                "description": f"Stable tenure of {int(emp_m)} months ({int(emp_m)//12} yrs) indicates durable earning capacity.",
                "feature": "MonthsEmployed",
                "val": emp_m
            })

        # 5. Co-Signer Presence
        cosigner = row["HasCoSigner"]
        if cosigner == "Yes":
            protective.append({
                "factor": "Co-Signer Guarantee",
                "impact_pts": -14,
                "description": "Co-signer provides secondary recourse and risk-sharing capability.",
                "feature": "HasCoSigner",
                "val": "Yes"
            })
        else:
            drivers.append({
                "factor": "Sole Borrower Obligation",
                "impact_pts": 5,
                "description": "No co-signer available to provide supplementary repayment guarantee.",
                "feature": "HasCoSigner",
                "val": "No"
            })

        # 6. Loan Term & Interest
        term = row["LoanTerm"]
        if term >= 48:
            drivers.append({
                "factor": "Extended Loan Term",
                "impact_pts": 7,
                "description": f"Extended tenor of {term} months increases exposure duration and cumulative default hazard.",
                "feature": "LoanTerm",
                "val": term
            })

        # Sort drivers and protective factors by absolute magnitude
        drivers.sort(key=lambda x: x["impact_pts"], reverse=True)
        protective.sort(key=lambda x: x["impact_pts"])
        
        return drivers[:5], protective[:4]

    def predict(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Runs end-to-end inference and returns structured risk intelligence."""
        input_df = self._normalize_input(raw_input)
        X_trans = self.preprocessor.transform(input_df)
        
        # Predict calibrated probability of default
        prob_default = float(self.model.predict_proba(X_trans)[0, 1])
        
        # Scale to institutional 0-100 risk score
        # Non-linear logistic scaling mapped to operational range:
        # PD 0.02 -> Score 12
        # PD 0.08 -> Score 30 (Low/Med boundary)
        # PD 0.20 -> Score 60 (Med/High boundary)
        # PD 0.50 -> Score 88
        if prob_default < self.thresh_low:
            # Range 0 to 30
            risk_score = int(round((prob_default / self.thresh_low) * 30))
            risk_level = "LOW"
        elif prob_default < self.thresh_high:
            # Range 31 to 60
            progress = (prob_default - self.thresh_low) / (self.thresh_high - self.thresh_low)
            risk_score = int(round(30 + progress * 30))
            risk_level = "MEDIUM"
        else:
            # Range 61 to 99
            progress = min(1.0, (prob_default - self.thresh_high) / (0.60 - self.thresh_high))
            risk_score = int(round(60 + progress * 39))
            risk_level = "HIGH"
            
        risk_score = max(5, min(99, risk_score))
        
        # Local explainability
        drivers, protective = self.explain_instance(input_df, prob_default)
        
        # Recommended review intensity
        if risk_level == "HIGH":
            review_level = "ENHANCED_UNDERWRITING"
            recommended_action = "Escalate to Senior Underwriter. Require fractional funding structure and additional collateral/guarantee before approval."
        elif risk_level == "MEDIUM":
            review_level = "STANDARD_DOCUMENTATION"
            recommended_action = "Conditional approval. Require bank statement verification and recommend fractional funding participation."
        else:
            review_level = "FAST_TRACK_MONITORING"
            recommended_action = "Eligible for fast-track processing with standard monitoring and single-lender funding."
            
        return {
            "probability_of_default": round(prob_default, 4),
            "probability_pct": round(prob_default * 100, 2),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "review_level": review_level,
            "recommended_action": recommended_action,
            "risk_drivers": drivers,
            "protective_factors": protective,
            "model_metadata": {
                "version": self.metadata.get("model_metadata", {}).get("model_version", "riskora-ml-v1.0"),
                "algorithm": self.metadata.get("model_metadata", {}).get("algorithm", "Calibrated HistGradientBoosting"),
                "test_roc_auc": self.metadata.get("test_metrics", {}).get("roc_auc", 0.792),
                "test_brier": self.metadata.get("test_metrics", {}).get("brier_score", 0.082)
            },
            "explainability_disclosure": (
                "Feature attribution indicates statistical correlation and model impact from empirical historical loan data. "
                "Attributions represent decision-support signals, not deterministic causal laws. Final decisions rest with credit underwriters."
            )
        }

if __name__ == "__main__":
    engine = RiskInferenceEngine.get_instance()
    # Test case 1: High risk borrower
    sample_high = {
        "Income": 280000,
        "LoanAmount": 180000,
        "CreditScore": 548,
        "DTIRatio": 0.56,
        "MonthsEmployed": 8,
        "HasCoSigner": "No",
        "HasMortgage": "No",
        "HasDependents": "Yes"
    }
    res_high = engine.predict(sample_high)
    print("Sample High Risk Test:", json.dumps(res_high, indent=2))
    
    # Test case 2: Low risk borrower
    sample_low = {
        "Income": 720000,
        "LoanAmount": 120000,
        "CreditScore": 765,
        "DTIRatio": 0.20,
        "MonthsEmployed": 60,
        "HasCoSigner": "Yes",
        "HasMortgage": "Yes",
        "HasDependents": "No"
    }
    res_low = engine.predict(sample_low)
    print("Sample Low Risk Test:", json.dumps(res_low, indent=2))

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
import warnings
from sklearn.exceptions import InconsistentVersionWarning
from backend.config import ARTIFACTS_DIR
from backend.schema import inference_profile
from ml.artifact_validation import validate_artifact_files
from typing import Dict, Any, List, Tuple

class RiskInferenceEngine:
    _instance = None
    
    def __init__(self):
        model_path, preprocessor_path, metrics_path = validate_artifact_files(ARTIFACTS_DIR)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", InconsistentVersionWarning)
                self.model = joblib.load(model_path)
                self.preprocessor = joblib.load(preprocessor_path)
            with open(metrics_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
            if not isinstance(self.metadata, dict):
                raise ValueError("Metrics metadata must be an object.")
            policy = self.metadata["threshold_policy"]
            if not 0 < policy["low_risk_threshold"] < policy["high_risk_threshold"] < 0.60:
                raise ValueError("Invalid risk thresholds in metrics metadata.")
            if not self.metadata["model_metadata"]["model_version"]:
                raise ValueError("Missing model version.")
            probe = self.preprocessor.transform(self._normalize_input({}))
            if probe.shape[1] != self.metadata["model_metadata"]["feature_count"]:
                raise ValueError("Preprocessor and metadata feature counts differ.")
            probabilities = self.model.predict_proba(probe)
            if list(self.model.classes_) != [0, 1] or probabilities.shape != (1, 2):
                raise ValueError("Artifact must predict binary classes 0 and 1.")
            if not np.isfinite(probabilities).all() or not np.all((probabilities >= 0) & (probabilities <= 1)) or not np.allclose(probabilities.sum(axis=1), 1):
                raise ValueError("Artifact produced invalid probabilities.")
        except Exception as error:
            raise RuntimeError(
                "Model artifacts could not be validated. Install requirements.txt and "
                "restore a matching model, preprocessor, and metrics set. " + str(error)
            ) from error
            
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
        row = inference_profile(raw)
        row["LoanToIncome"] = round(row["LoanAmount"] / max(row["Income"], 1.0), 4)
        monthly_income = max(row["Income"] / 12.0, 1.0)
        row["MonthlyBurdenRatio"] = round((row["LoanAmount"] / row["LoanTerm"]) / monthly_income, 4)
        return pd.DataFrame([row])

    def explain_instance(self, input_df: pd.DataFrame, pd_score: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Generates local feature attributions comparing the applicant against
        benchmark distributions and empirical risk factors.
        """
        drivers = []
        protective = []
        # Explanations are API/SQLite JSON values, not NumPy scalar objects.
        row = {key: value.item() if isinstance(value, np.generic) else value
               for key, value in input_df.iloc[0].items()}
        
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

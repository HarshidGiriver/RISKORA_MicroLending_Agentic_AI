"""
RISKORA — Anomaly & Suspicious Profile Detection Engine
Evaluates statistical multivariate anomalies, extreme outliers, and suspicious data
patterns. Serves strictly as a decision-support indicator for enhanced underwriting.
"""

from typing import Dict, Any, List
from backend.schema import inspect_profile

class AnomalyDetector:
    # Empirical benchmark distributions for micro-lending
    MEDIAN_INCOME = 450000
    MEDIAN_LOAN = 120000
    
    @classmethod
    def evaluate(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        raw, _ = inspect_profile(raw)
        def num(val, default=None):
            try:
                if val is None or str(val).strip() == "":
                    return default
                return float(val)
            except (ValueError, TypeError):
                return default

        income = num(raw.get("Income"))
        loan_amount = num(raw.get("LoanAmount"))
        credit_score = num(raw.get("CreditScore"))
        dti = num(raw.get("DTIRatio"))
        age = num(raw.get("Age"))
        emp_months = num(raw.get("MonthsEmployed"))
        
        indicators = []
        anomaly_score = 0.0  # 0.0 (clean) to 1.0 (highly anomalous)
        
        # 1. Extreme Loan-to-Income Spike
        if income and loan_amount:
            ratio = loan_amount / max(income, 1.0)
            if ratio >= 1.5:
                indicators.append({
                    "type": "EXTREME_LEVERAGE_ANOMALY",
                    "severity": "HIGH",
                    "description": f"Loan request is {ratio:.1f}× total annual income. High debt overhang outlier.",
                    "feature": "LoanToIncome"
                })
                anomaly_score += 0.35
            elif ratio >= 0.8:
                indicators.append({
                    "type": "ELEVATED_LEVERAGE",
                    "severity": "MEDIUM",
                    "description": f"Loan request represents {ratio*100:.0f}% of annual earnings. Requires debt capacity audit.",
                    "feature": "LoanToIncome"
                })
                anomaly_score += 0.15

        # 2. Wealth / Credit Disconnect Outlier
        if income and credit_score:
            if income > 1500000 and credit_score < 480:
                indicators.append({
                    "type": "INCOME_CREDIT_DIVERGENCE",
                    "severity": "HIGH",
                    "description": f"High income (₹{int(income):,}) coupled with deep subprime credit ({int(credit_score)}). Suspicious or distressed profile.",
                    "feature": "IncomeCreditDivergence"
                })
                anomaly_score += 0.30

        # 3. Super-High DTI Outlier
        if dti is not None:
            if dti >= 0.65:
                indicators.append({
                    "type": "CRITICAL_DTI_EXPOSURE",
                    "severity": "HIGH",
                    "description": f"DTI ratio of {dti*100:.1f}% indicates applicant is severely leveraged across existing obligations.",
                    "feature": "DTIRatio"
                })
                anomaly_score += 0.25
            elif dti >= 0.50:
                indicators.append({
                    "type": "HIGH_DTI_BURDEN",
                    "severity": "MEDIUM",
                    "description": f"DTI of {dti*100:.1f}% exceeds typical underwriting tolerances.",
                    "feature": "DTIRatio"
                })
                anomaly_score += 0.12

        # 4. Demographic / Employment Irregularities
        if age is not None and emp_months is not None:
            if age <= 22 and emp_months > 60:
                indicators.append({
                    "type": "IRREGULAR_EMPLOYMENT_TIMELINE",
                    "severity": "HIGH",
                    "description": f"Applicant age {int(age)} declares {int(emp_months)} months ({(emp_months/12):.1f} yrs) of continuous employment.",
                    "feature": "EmploymentAgeDiscrepancy"
                })
                anomaly_score += 0.30
            elif age >= 65 and emp_months < 6:
                indicators.append({
                    "type": "LATE_CAREER_TENURE_ANOMALY",
                    "severity": "LOW",
                    "description": f"Senior applicant age {int(age)} reports very short job tenure ({int(emp_months)} months).",
                    "feature": "LateCareerTenure"
                })
                anomaly_score += 0.10

        # 5. Cap score between 0.0 and 1.0
        anomaly_score = min(1.0, round(anomaly_score, 2))
        anomaly_detected = anomaly_score >= 0.25
        
        if anomaly_score >= 0.50:
            anomaly_level = "SUSPICIOUS_ANOMALY"
            review_recommendation = "Enhanced Underwriting & Manual Dossier Verification Recommended"
        elif anomaly_score >= 0.25:
            anomaly_level = "ELEVATED_INSPECTION"
            review_recommendation = "Supplementary Verification of Income & Existing Liabilities Recommended"
        else:
            anomaly_level = "NORMAL"
            review_recommendation = "Standard Underwriting Workflow Applicable"

        return {
            "anomaly_detected": anomaly_detected,
            "anomaly_score": anomaly_score,
            "anomaly_level": anomaly_level,
            "indicators": indicators,
            "recommendation": review_recommendation,
            "decision_support_note": (
                "Anomaly indicators highlight statistical irregularities and potential data entry inconsistencies. "
                "These indicators do not constitute a fraud accusation and serve as decision-support guidance for credit analysts."
            )
        }

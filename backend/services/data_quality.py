"""
RISKORA — Data Quality Engine
Independently evaluates borrower dataset completeness, validity bounds,
and logical contradictions. Keeps data quality strictly separated from default risk.
"""

from typing import Dict, Any, List, Tuple

class DataQualityEngine:
    REQUIRED_FIELDS = [
        ("Income", ["Income", "income", "annualIncome"], "Annual verified income"),
        ("LoanAmount", ["LoanAmount", "loanAmount", "amount"], "Requested loan principal"),
        ("CreditScore", ["CreditScore", "creditScore", "credit"], "Bureau credit score"),
        ("DTIRatio", ["DTIRatio", "dtiRatio", "dti"], "Debt-to-Income ratio"),
        ("LoanTerm", ["LoanTerm", "loanTerm", "term"], "Loan repayment term"),
        ("MonthsEmployed", ["MonthsEmployed", "monthsEmployed", "empMonths"], "Employment tenure (months)"),
        ("NumCreditLines", ["NumCreditLines", "numCreditLines", "creditLines"], "Active credit lines count"),
        ("InterestRate", ["InterestRate", "interestRate", "rate"], "Offered annual interest rate")
    ]
    
    OPTIONAL_FIELDS = [
        ("Education", ["Education", "education"], "Highest education credential"),
        ("EmploymentType", ["EmploymentType", "employmentType", "employment"], "Employment arrangement"),
        ("MaritalStatus", ["MaritalStatus", "maritalStatus"], "Marital status"),
        ("HasMortgage", ["HasMortgage", "hasMortgage"], "Existing residential mortgage"),
        ("HasDependents", ["HasDependents", "hasDependents"], "Declared dependents"),
        ("LoanPurpose", ["LoanPurpose", "loanPurpose", "purpose"], "Declared loan purpose"),
        ("HasCoSigner", ["HasCoSigner", "hasCoSigner", "hasCosigner"], "Co-signer guarantee declaration")
    ]

    @classmethod
    def evaluate(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        def get_val(keys):
            for k in keys:
                if k in raw and raw[k] is not None and str(raw[k]).strip() != "":
                    return raw[k]
            return None

        missing_required = []
        available_required = 0
        for std_name, aliases, desc in cls.REQUIRED_FIELDS:
            val = get_val(aliases)
            if val is None:
                missing_required.append(f"{desc} ({std_name})")
            else:
                available_required += 1

        missing_optional = []
        available_optional = 0
        for std_name, aliases, desc in cls.OPTIONAL_FIELDS:
            val = get_val(aliases)
            if val is None:
                missing_optional.append(f"{desc} ({std_name})")
            else:
                available_optional += 1

        total_fields = len(cls.REQUIRED_FIELDS) + len(cls.OPTIONAL_FIELDS)
        total_available = available_required + available_optional
        completeness_pct = round((total_available / total_fields) * 100, 1)
        
        validity_warnings = []
        contradictions = []
        
        # 1. Validity Range Checks
        age_val = get_val(["Age", "age"])
        if age_val is not None:
            try:
                age = float(age_val)
                if age < 18 or age > 95:
                    validity_warnings.append(f"Declared age {int(age)} is outside admissible range [18, 95].")
            except (ValueError, TypeError):
                validity_warnings.append(f"Invalid non-numeric age format: {age_val}")

        inc_val = get_val(["Income", "income", "annualIncome"])
        income = None
        if inc_val is not None:
            try:
                income = float(inc_val)
                if income <= 0:
                    validity_warnings.append("Annual income must be strictly positive.")
                elif income < 50000:
                    validity_warnings.append(f"Annual income ₹{int(income):,} is below micro-lending minimum verification threshold.")
            except (ValueError, TypeError):
                validity_warnings.append(f"Invalid non-numeric income format: {inc_val}")

        loan_val = get_val(["LoanAmount", "loanAmount", "amount"])
        loan_amount = None
        if loan_val is not None:
            try:
                loan_amount = float(loan_val)
                if loan_amount <= 0:
                    validity_warnings.append("Loan principal must be strictly positive.")
                elif loan_amount > 5000000:
                    validity_warnings.append(f"Loan amount ₹{int(loan_amount):,} exceeds micro-lending portfolio cap (₹50,00,000).")
            except (ValueError, TypeError):
                validity_warnings.append(f"Invalid non-numeric loan amount: {loan_val}")

        cs_val = get_val(["CreditScore", "creditScore", "credit"])
        credit_score = None
        if cs_val is not None:
            try:
                credit_score = float(cs_val)
                if credit_score < 300 or credit_score > 850:
                    validity_warnings.append(f"Credit score {int(credit_score)} is outside standard bureau range [300, 850].")
            except (ValueError, TypeError):
                validity_warnings.append(f"Invalid non-numeric credit score: {cs_val}")

        dti_val = get_val(["DTIRatio", "dtiRatio", "dti"])
        dti_ratio = None
        if dti_val is not None:
            try:
                dti_ratio = float(dti_val)
                if dti_ratio < 0.0 or dti_ratio > 1.5:
                    validity_warnings.append(f"Debt-to-Income ratio {dti_ratio} is outside feasible boundary [0.0, 1.5].")
            except (ValueError, TypeError):
                validity_warnings.append(f"Invalid non-numeric DTI ratio: {dti_val}")

        emp_m_val = get_val(["MonthsEmployed", "monthsEmployed", "empMonths"])
        months_employed = None
        if emp_m_val is not None:
            try:
                months_employed = float(emp_m_val)
                if months_employed < 0:
                    validity_warnings.append("Months employed cannot be negative.")
            except (ValueError, TypeError):
                validity_warnings.append(f"Invalid non-numeric employment tenure: {emp_m_val}")

        # 2. Contradiction & Cross-Field Consistency Checks
        if age_val is not None and months_employed is not None:
            max_possible_tenure = max(0, (float(age_val) - 16) * 12)
            if months_employed > max_possible_tenure:
                contradictions.append(
                    f"Employment tenure ({int(months_employed)} months) exceeds working lifetime for age {int(age_val)}."
                )

        emp_type = get_val(["EmploymentType", "employmentType", "employment"])
        if emp_type == "Unemployed" and months_employed is not None and months_employed > 0:
            contradictions.append("Applicant classified as Unemployed but reports positive employment tenure.")

        cl_val = get_val(["NumCreditLines", "numCreditLines", "creditLines"])
        if cl_val is not None and dti_ratio is not None:
            try:
                cl = float(cl_val)
                if cl == 0 and dti_ratio > 0.35:
                    contradictions.append(f"High DTI ratio ({dti_ratio*100:.1f}%) reported with zero recorded credit lines.")
            except (ValueError, TypeError):
                pass

        if income is not None and loan_amount is not None:
            cosigner_val = str(get_val(["HasCoSigner", "hasCoSigner", "hasCosigner"]) or "").lower()
            if loan_amount > income * 2.5 and cosigner_val not in ["yes", "true", "1"]:
                validity_warnings.append(
                    f"Loan amount is {loan_amount/income:.1f}× annual income without a registered co-signer."
                )

        # 3. Overall Data Quality Score Calculation
        # Base: Completeness of required (65%) + completeness of optional (15%)
        req_score = (available_required / len(cls.REQUIRED_FIELDS)) * 65.0
        opt_score = (available_optional / len(cls.OPTIONAL_FIELDS)) * 15.0
        
        # Deductions for validity warnings (-5 pts each) and contradictions (-12 pts each)
        penalty = (len(validity_warnings) * 5.0) + (len(contradictions) * 12.0)
        
        final_dq_score = max(10, min(100, round(req_score + opt_score + 20.0 - penalty)))
        
        if final_dq_score >= 88:
            quality_tier = "EXCELLENT"
        elif final_dq_score >= 70:
            quality_tier = "ACCEPTABLE"
        elif final_dq_score >= 50:
            quality_tier = "DEGRADED"
        else:
            quality_tier = "CRITICAL_GAPS"

        return {
            "data_quality_score": final_dq_score,
            "quality_tier": quality_tier,
            "completeness_pct": completeness_pct,
            "available_fields_count": total_available,
            "total_fields_count": total_fields,
            "missing_required_fields": missing_required,
            "missing_optional_fields": missing_optional,
            "validity_warnings": validity_warnings,
            "contradiction_flags": contradictions,
            "verification_ready": len(missing_required) == 0 and len(contradictions) == 0
        }

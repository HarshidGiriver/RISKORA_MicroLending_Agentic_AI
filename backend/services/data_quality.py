"""Input completeness and consistency checks, independent of default risk."""
from backend.schema import ALIASES, REQUIRED, OPTIONAL, inspect_profile


class DataQualityEngine:
    REQUIRED_FIELDS = [(field, list(ALIASES[field]), field) for field in REQUIRED]
    OPTIONAL_FIELDS = [(field, list(ALIASES[field]), field) for field in OPTIONAL]

    @classmethod
    def evaluate(cls, raw):
        values, warnings = inspect_profile(raw)
        missing_required = [field for field in REQUIRED if values.get(field) is None]
        missing_optional = [field for field in OPTIONAL if values.get(field) is None]
        required_count = len(REQUIRED) - len(missing_required)
        optional_count = len(OPTIONAL) - len(missing_optional)
        contradictions = []
        age, months = values.get("Age"), values.get("MonthsEmployed")
        if age is not None and months is not None and months > max(0, (age - 16) * 12):
            contradictions.append("Employment tenure exceeds the applicant's working lifetime.")
        if values.get("EmploymentType") == "Unemployed" and months is not None and months > 0:
            contradictions.append("Unemployed applicant reports positive employment tenure.")
        dti = values.get("DTIRatio")
        if values.get("NumCreditLines") == 0 and dti is not None and dti > 0.35:
            contradictions.append("High DTI is reported with zero recorded credit lines.")
        income, amount = values.get("Income"), values.get("LoanAmount")
        if income is not None and income < 50000:
            warnings.append("Annual income is below the demo verification threshold of 50000.")
        if income is not None and amount is not None and amount > income * 2.5 and values.get("HasCoSigner") != "Yes":
            warnings.append(f"Loan amount is {amount / income:.1f} times annual income without a co-signer.")
        score = max(10, min(100, round(
            required_count / len(REQUIRED) * 65
            + optional_count / len(OPTIONAL) * 15 + 20
            - len(warnings) * 5 - len(contradictions) * 12
        )))
        tier = ("EXCELLENT" if score >= 88 else "ACCEPTABLE" if score >= 70
                else "DEGRADED" if score >= 50 else "CRITICAL_GAPS")
        total = len(REQUIRED) + len(OPTIONAL)
        return {
            "data_quality_score": score,
            "quality_tier": tier,
            "completeness_pct": round((required_count + optional_count) / total * 100, 1),
            "available_fields_count": required_count + optional_count,
            "total_fields_count": total,
            "missing_required_fields": missing_required,
            "missing_optional_fields": missing_optional,
            "validity_warnings": warnings,
            "contradiction_flags": contradictions,
            "verification_ready": not (missing_required or warnings or contradictions),
        }

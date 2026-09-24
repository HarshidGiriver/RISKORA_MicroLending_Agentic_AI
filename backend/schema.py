"""Shared borrower/loan field mapping and validation for storage and analytics.

Canonical names match the training dataset. Missing values remain missing until
the inference adapter supplies its explicitly documented fallback values.
"""
import math

ALIASES = {
    "Age": ("Age", "age"),
    "Income": ("Income", "income", "annualIncome"),
    "LoanAmount": ("LoanAmount", "loan_amount", "loanAmount", "amount"),
    "CreditScore": ("CreditScore", "credit_score", "creditScore", "credit"),
    "MonthsEmployed": ("MonthsEmployed", "months_employed", "monthsEmployed", "empMonths"),
    "NumCreditLines": ("NumCreditLines", "num_credit_lines", "numCreditLines", "creditLines"),
    "InterestRate": ("InterestRate", "interest_rate", "interestRate", "rate"),
    "LoanTerm": ("LoanTerm", "loan_term", "loanTerm", "term"),
    "DTIRatio": ("DTIRatio", "dti_ratio", "dtiRatio", "dti"),
    "Education": ("Education", "education"),
    "EmploymentType": ("EmploymentType", "employment_type", "employmentType", "employment"),
    "MaritalStatus": ("MaritalStatus", "marital_status", "maritalStatus"),
    "HasMortgage": ("HasMortgage", "has_mortgage", "hasMortgage"),
    "HasDependents": ("HasDependents", "has_dependents", "hasDependents"),
    "LoanPurpose": ("LoanPurpose", "loan_purpose", "loanPurpose", "purpose"),
    "HasCoSigner": ("HasCoSigner", "has_cosigner", "hasCoSigner", "hasCosigner"),
}
NUMERIC = {
    "Age": (18, 95, True),
    "Income": (1, 5_000_000, False),
    "LoanAmount": (0.01, 5_000_000, False),
    "CreditScore": (300, 850, True),
    "MonthsEmployed": (0, 948, True),
    "NumCreditLines": (0, 25, True),
    "InterestRate": (0, 100, False),
    "LoanTerm": (1, 120, True),
    "DTIRatio": (0, 1.5, False),
}
CATEGORIES = {
    "Education": ("High School", "Bachelor's", "Master's", "PhD"),
    "EmploymentType": ("Salaried", "Self-employed", "Contract", "Unemployed"),
    "MaritalStatus": ("Single", "Married", "Divorced"),
    "LoanPurpose": ("Business", "Education", "Home", "Auto", "Other"),
    "HasMortgage": ("Yes", "No"),
    "HasDependents": ("Yes", "No"),
    "HasCoSigner": ("Yes", "No"),
}
REQUIRED = ("Income", "LoanAmount", "CreditScore", "DTIRatio", "LoanTerm",
            "MonthsEmployed", "NumCreditLines", "InterestRate")
OPTIONAL = tuple(CATEGORIES)
DEFAULTS = {
    "Age": 35, "Income": 450000, "LoanAmount": 120000, "CreditScore": 650,
    "MonthsEmployed": 36, "NumCreditLines": 4, "InterestRate": 12.5,
    "LoanTerm": 36, "DTIRatio": 0.32, "Education": "Bachelor's",
    "EmploymentType": "Salaried", "MaritalStatus": "Married", "HasMortgage": "No",
    "HasDependents": "No", "LoanPurpose": "Business", "HasCoSigner": "No",
}


class ProfileValidationError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors))


def _convert(field, value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if field in NUMERIC:
        low, high, integer = NUMERIC[field]
        try:
            number = float(value)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(f"{field} must be a finite number.") from None
        if isinstance(value, bool) or not math.isfinite(number):
            raise ValueError(f"{field} must be a finite number.")
        if not low <= number <= high or (integer and not number.is_integer()):
            kind = "integer" if integer else "number"
            raise ValueError(f"{field} must be a {kind} between {low} and {high}.")
        return int(number) if integer else number
    text = str(value).strip()
    if field in ("HasMortgage", "HasDependents", "HasCoSigner"):
        text = {"true": "Yes", "1": "Yes", "false": "No", "0": "No"}.get(text.lower(), text)
    choices = {choice.casefold(): choice for choice in CATEGORIES[field]}
    if text.casefold() not in choices:
        raise ValueError(f"{field} must be one of: {', '.join(CATEGORIES[field])}.")
    return choices[text.casefold()]


def inspect_profile(raw):
    """Return canonical typed values plus errors, without inventing missing data."""
    if not isinstance(raw, dict):
        return {}, ["Borrower profile must be a JSON object."]
    values, errors = {}, []
    for field, aliases in ALIASES.items():
        supplied = [raw[key] for key in aliases if key in raw]
        if not supplied:
            continue
        try:
            converted = [_convert(field, value) for value in supplied]
            if any(value != converted[0] for value in converted[1:]):
                raise ValueError(f"Conflicting aliases supplied for {field}.")
            values[field] = converted[0]
        except ValueError as error:
            values[field] = None
            errors.append(str(error))
    return values, errors


def validate_profile(raw, require_required=False):
    values, errors = inspect_profile(raw)
    if require_required:
        errors.extend(f"{field} is required." for field in REQUIRED if values.get(field) is None)
    if errors:
        raise ProfileValidationError(errors)
    return values


def merge_profiles(base, overrides):
    """Normalize each layer before merging so aliases override saved values correctly."""
    return {**validate_profile(base), **validate_profile(overrides)}


def inference_profile(raw):
    values = validate_profile(raw)
    return {field: values.get(field) if values.get(field) is not None else default
            for field, default in DEFAULTS.items()}

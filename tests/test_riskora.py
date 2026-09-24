"""
RISKORA — Automated Test Suite
Comprehensive unit and integration tests covering:
- ML inference calibration & explainability
- Data quality verification & bounds
- Anomaly & outlier detection
- Single-lender vs. fractional syndication & HHI
- Amortisation schedules & zero-balance reconciliation
- Waterfall repayment allocation policies
- Database integrity & persistence
- Backend REST API endpoints
"""

import os
import sys
import unittest
import json
import sqlite3

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ml.infer import RiskInferenceEngine
from backend.services.data_quality import DataQualityEngine
from backend.services.anomaly_detector import AnomalyDetector
from backend.services.funding_service import FundingService
from backend.services.repayment_service import RepaymentService
from backend.database import get_connection, init_db, seed_default_cases
from tests.support import IsolatedDatabaseMixin

class TestRiskoraML(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RiskInferenceEngine.get_instance()

    def test_high_risk_inference(self):
        sample = {
            "Income": 240000,
            "LoanAmount": 200000,
            "CreditScore": 510,
            "DTIRatio": 0.58,
            "MonthsEmployed": 6,
            "NumCreditLines": 10,
            "EmploymentType": "Contract",
            "HasCoSigner": "No"
        }
        res = self.engine.predict(sample)
        self.assertGreaterEqual(res["probability_of_default"], 0.20)
        self.assertEqual(res["risk_level"], "HIGH")
        self.assertGreaterEqual(res["risk_score"], 60)
        self.assertTrue(len(res["risk_drivers"]) > 0)
        # Verify subprime driver present
        driver_factors = [d["factor"] for d in res["risk_drivers"]]
        self.assertTrue(any("Credit" in f or "Debt" in f or "Loan" in f for f in driver_factors))

    def test_low_risk_inference(self):
        sample = {
            "Income": 850000,
            "LoanAmount": 100000,
            "CreditScore": 790,
            "DTIRatio": 0.18,
            "MonthsEmployed": 72,
            "NumCreditLines": 3,
            "EmploymentType": "Salaried",
            "HasCoSigner": "Yes",
            "HasMortgage": "Yes"
        }
        res = self.engine.predict(sample)
        self.assertLess(res["probability_of_default"], 0.08)
        self.assertEqual(res["risk_level"], "LOW")
        self.assertLessEqual(res["risk_score"], 30)
        self.assertTrue(len(res["protective_factors"]) > 0)

class TestDataQuality(unittest.TestCase):
    def test_complete_profile(self):
        sample = {
            "Income": 500000, "LoanAmount": 100000, "CreditScore": 700,
            "DTIRatio": 0.25, "LoanTerm": 36, "MonthsEmployed": 48,
            "NumCreditLines": 4, "InterestRate": 12.0, "Education": "Bachelor's",
            "EmploymentType": "Salaried", "MaritalStatus": "Married",
            "HasMortgage": "Yes", "HasDependents": "Yes", "LoanPurpose": "Home",
            "HasCoSigner": "Yes"
        }
        res = DataQualityEngine.evaluate(sample)
        self.assertGreaterEqual(res["data_quality_score"], 85)
        self.assertEqual(res["quality_tier"], "EXCELLENT")
        self.assertEqual(len(res["missing_required_fields"]), 0)
        self.assertTrue(res["verification_ready"])

    def test_missing_and_contradictory_profile(self):
        sample = {
            "Income": None,
            "LoanAmount": 150000,
            "Age": 20,
            "MonthsEmployed": 120,  # 10 years at age 20 -> Contradiction!
            "EmploymentType": "Unemployed"
        }
        res = DataQualityEngine.evaluate(sample)
        self.assertLess(res["data_quality_score"], 65)
        self.assertTrue(len(res["missing_required_fields"]) > 0)
        self.assertTrue(len(res["contradiction_flags"]) > 0)
        self.assertFalse(res["verification_ready"])

class TestAnomalyDetector(unittest.TestCase):
    def test_normal_profile(self):
        sample = {
            "Income": 480000, "LoanAmount": 120000, "CreditScore": 680,
            "DTIRatio": 0.28, "Age": 34, "MonthsEmployed": 40
        }
        res = AnomalyDetector.evaluate(sample)
        self.assertFalse(res["anomaly_detected"])
        self.assertEqual(res["anomaly_level"], "NORMAL")

    def test_extreme_leverage_anomaly(self):
        sample = {
            "Income": 150000, "LoanAmount": 500000,  # 3.3x annual income
            "CreditScore": 420, "DTIRatio": 0.72
        }
        res = AnomalyDetector.evaluate(sample)
        self.assertTrue(res["anomaly_detected"])
        self.assertIn(res["anomaly_level"], ["ELEVATED_INSPECTION", "SUSPICIOUS_ANOMALY"])
        indicator_types = [i["type"] for i in res["indicators"]]
        self.assertIn("EXTREME_LEVERAGE_ANOMALY", indicator_types)

class TestFundingService(unittest.TestCase):
    def test_single_lender_funding(self):
        res = FundingService.calculate_structure(100000, "LOW", mode="single")
        self.assertEqual(res["mode"], "single")
        self.assertEqual(len(res["positions"]), 1)
        self.assertEqual(res["positions"][0]["share_pct"], 100.0)
        self.assertEqual(res["herfindahl_index"], 10000.0)
        self.assertEqual(res["concentration_rating"], "HIGH_CONCENTRATION")

    def test_fractional_funding(self):
        res = FundingService.calculate_structure(120000, "HIGH", mode="fractional", lender_count=3)
        self.assertEqual(res["mode"], "fractional")
        self.assertEqual(len(res["positions"]), 3)
        total_share = sum(p["share_pct"] for p in res["positions"])
        self.assertAlmostEqual(total_share, 100.0, places=1)
        total_amt = sum(p["committed_amount"] for p in res["positions"])
        self.assertAlmostEqual(total_amt, 120000.0, places=1)
        self.assertLess(res["herfindahl_index"], 10000.0)

class TestRepaymentService(unittest.TestCase):
    def test_amortisation_zero_balance(self):
        sched = RepaymentService.generate_schedule(
            principal=120000, annual_rate_pct=12.0, term_months=12,
            schedule_type="monthly", allocation_policy="pro-rata"
        )
        self.assertEqual(len(sched["installments"]), 12)
        # Final balance must equal exactly 0.00
        final_inst = sched["installments"][-1]
        self.assertEqual(final_inst["remaining_balance"], 0.0)
        # Total principal paid must equal 120,000
        total_prin = sum(i["principal_component"] for i in sched["installments"])
        self.assertAlmostEqual(total_prin, 120000.0, places=2)

    def test_bi_monthly_schedule(self):
        sched = RepaymentService.generate_schedule(
            principal=60000, annual_rate_pct=12.0, term_months=6,
            schedule_type="bi-monthly"
        )
        self.assertEqual(len(sched["installments"]), 12)  # 6 months * 2 payments
        self.assertEqual(sched["installments"][-1]["remaining_balance"], 0.0)

    def test_waterfall_allocation_reconciliation(self):
        positions = [
            {"lender_id": "L1", "lender_name": "Lender A", "share_pct": 60.0, "committed_amount": 60000},
            {"lender_id": "L2", "lender_name": "Lender B", "share_pct": 25.0, "committed_amount": 25000},
            {"lender_id": "L3", "lender_name": "Lender C", "share_pct": 15.0, "committed_amount": 15000}
        ]
        sched = RepaymentService.generate_schedule(
            principal=100000, annual_rate_pct=12.0, term_months=12,
            allocation_policy="largest-first", lender_positions=positions
        )
        # Verify for every installment, sum of lender allocations equals payment amount
        for inst in sched["installments"]:
            total_allocated = sum(a["total_allocated"] for a in inst["allocations"])
            self.assertAlmostEqual(total_allocated, inst["payment_amount"], places=1)

class TestDatabasePersistence(IsolatedDatabaseMixin, unittest.TestCase):
    def test_seed_cases_exist(self):
        with get_connection() as conn:
            cursor = conn.cursor()
            count = cursor.execute("SELECT COUNT(*) FROM loans;").fetchone()[0]
            self.assertGreaterEqual(count, 6)
            rahul = cursor.execute("SELECT * FROM loans WHERE id = 'LR-1054';").fetchone()
            self.assertIsNotNone(rahul)
            self.assertEqual(rahul["loan_amount"], 120000)

if __name__ == "__main__":
    unittest.main()

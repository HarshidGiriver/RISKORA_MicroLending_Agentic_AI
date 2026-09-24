"""
RISKORA — API Integration Tests
Tests REST endpoints using Tornado AsyncHTTPTestCase.
"""

import os
import sys
import json
import tornado.testing

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.server import make_app
from backend.database import init_db, seed_default_cases
from ml.infer import RiskInferenceEngine
from tests.support import IsolatedDatabaseMixin

class TestRiskoraAPI(IsolatedDatabaseMixin, tornado.testing.AsyncHTTPTestCase):
    @classmethod
    def setUpClass(cls):
        # Pre-load ML engine once to prevent first-call timeout
        RiskInferenceEngine.get_instance()

    def get_test_timeout(self):
        return 25.0

    def get_app(self):
        init_db()
        seed_default_cases()
        return make_app()

    def test_health_endpoint(self):
        response = self.fetch("/api/health")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["status"], "OPERATIONAL")

    def test_loans_list(self):
        response = self.fetch("/api/loans")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("loans", data)
        self.assertGreaterEqual(data["count"], 6)

    def test_loan_detail(self):
        response = self.fetch("/api/loans/LR-1054")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["id"], "LR-1054")
        self.assertEqual(data["borrower_name"], "Rahul P")

    def test_risk_analysis_endpoint(self):
        payload = {
            "loanId": "LR-1054",
            "Income": 280000,
            "LoanAmount": 120000,
            "CreditScore": 548,
            "DTIRatio": 0.52,
            "MonthsEmployed": 8,
            "NumCreditLines": 9
        }
        response = self.fetch("/api/risk/analyze", method="POST", body=json.dumps(payload))
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("probability_of_default", data)
        self.assertIn("risk_score", data)
        self.assertIn("risk_drivers", data)
        self.assertIn("data_quality", data)
        self.assertIn("anomaly_indicators", data)

    def test_scenario_simulate_endpoint(self):
        payload = {
            "baseLoanId": "LR-1054",
            "scenario": {
                "LoanAmount": 80000,
                "CreditScore": 680
            }
        }
        response = self.fetch("/api/risk/simulate", method="POST", body=json.dumps(payload))
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("base", data)
        self.assertIn("scenario", data)
        self.assertIn("comparison", data)

    def test_funding_optimize_endpoint(self):
        payload = {
            "loanId": "LR-1054",
            "amount": 120000,
            "riskLevel": "HIGH",
            "mode": "fractional",
            "lenderCount": 3
        }
        response = self.fetch("/api/funding/optimize", method="POST", body=json.dumps(payload))
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["mode"], "fractional")
        self.assertEqual(len(data["positions"]), 3)
        self.assertIn("herfindahl_index", data)

    def test_repayment_generate_endpoint(self):
        payload = {
            "loanId": "LR-1054",
            "principal": 120000,
            "rate": 12.0,
            "term": 12,
            "scheduleType": "monthly",
            "allocationPolicy": "pro-rata"
        }
        response = self.fetch("/api/repayment/generate", method="POST", body=json.dumps(payload))
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("installments", data)
        self.assertEqual(len(data["installments"]), 12)

    def test_dataset_explorer_endpoint(self):
        response = self.fetch("/api/dataset/explorer?page=1&limit=10")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("rows", data)
        self.assertEqual(len(data["rows"]), 10)
        self.assertIn("summary_stats", data)

    def test_repayment_record_payment(self):
        # 1. First generate a schedule for LR-1054
        gen_payload = {
            "loanId": "LR-1054",
            "principal": 120000,
            "rate": 12.0,
            "term": 12,
            "scheduleType": "monthly",
            "allocationPolicy": "pro-rata"
        }
        self.fetch("/api/repayment/generate", method="POST", body=json.dumps(gen_payload))
        
        # 2. Record payment for installment #1
        pay_payload = {
            "loanId": "LR-1054",
            "installmentNum": 1,
            "amount": 10661.85
        }
        response = self.fetch("/api/repayment/record", method="POST", body=json.dumps(pay_payload))
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["success"])
        self.assertEqual(data["payment"]["status"], "PAID")
        self.assertIn("paid_at", data["payment"])

    def test_repayment_record_fallback(self):
        # Record payment for loan without existing schedule (LR-1048)
        pay_payload = {
            "loanId": "LR-1048",
            "installmentNum": 1
        }
        response = self.fetch("/api/repayment/record", method="POST", body=json.dumps(pay_payload))
        self.assertEqual(response.code, 409)
        data = json.loads(response.body)
        self.assertIn("schedule", data["error"])

if __name__ == "__main__":
    tornado.testing.main()

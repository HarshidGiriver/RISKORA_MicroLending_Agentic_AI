"""Regression coverage for the first correctness/setup milestone."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tornado.testing import AsyncHTTPTestCase
from backend import database
from backend.config import PROJECT_ROOT, ARTIFACTS_DIR
from backend.schema import validate_profile, ProfileValidationError
from backend.server import make_app, DatasetExplorerHandler
from backend.services.data_quality import DataQualityEngine
from backend.services.anomaly_detector import AnomalyDetector
from ml.infer import RiskInferenceEngine
from ml.artifact_validation import ARTIFACT_NAMES, validate_artifact_files
from tests.support import IsolatedDatabaseMixin

COMPLETE_PROFILE = {
    "Age": 38, "Income": 720000, "LoanAmount": 40000, "CreditScore": 782,
    "DTIRatio": 0.16, "MonthsEmployed": 72, "NumCreditLines": 2,
    "InterestRate": 9.5, "LoanTerm": 12, "Education": "Master's",
    "EmploymentType": "Salaried", "MaritalStatus": "Married",
    "HasDependents": "Yes", "HasMortgage": "Yes", "HasCoSigner": "Yes",
    "LoanPurpose": "Education",
}


class FoundationAPITests(IsolatedDatabaseMixin, AsyncHTTPTestCase):
    @classmethod
    def setUpClass(cls):
        RiskInferenceEngine.get_instance()

    def get_app(self):
        return make_app()

    def get_test_timeout(self):
        return 30

    def post(self, path, body, expected=200):
        response = self.fetch(path, method="POST", body=json.dumps(body))
        self.assertEqual(response.code, expected, response.body.decode())
        return json.loads(response.body)

    def test_public_assets_work_private_files_are_blocked(self):
        for path in ("/", "/index.html", "/app.js", "/styles.css", "/assets/riskora-mark-white.png"):
            with self.subTest(path=path):
                self.assertEqual(self.fetch(path).code, 200)
        for path in ("/data/riskora.db", "/data/loan_default_full.csv", "/backend/server.py",
                     "/ml/artifacts/riskora_model.joblib", "/.git/config", "/.env",
                     "/assets/../data/riskora.db", "/assets/%2e%2e/data/riskora.db",
                     "/README.md", "/tests/test_foundation.py"):
            with self.subTest(path=path):
                self.assertIn(self.fetch(path).code, (403, 404))
        response = self.fetch("/api/loans", headers={"Origin": "https://example.invalid"})
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_create_and_reload_every_profile_field(self):
        profile = {**COMPLETE_PROFILE, "Education": "Bachelor's"}
        created = self.post("/api/loans", {"name": "O'Neil", **profile}, 201)
        loan = json.loads(self.fetch("/api/loans/" + created["loan_id"]).body)
        self.assertEqual(loan["borrower_name"], "O'Neil")
        self.assertEqual(validate_profile(loan), profile)
        self.assertEqual(loan["status"], "REQUEST_RECEIVED")
        again = self.post("/api/loans", {"name": "Second", **profile}, 201)
        self.assertNotEqual(created["loan_id"], again["loan_id"])

    def test_invalid_creation_is_atomic(self):
        with database.get_connection() as conn:
            before = [conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in ("borrowers", "loans")]
        for field, value in (("Income", 0), ("CreditScore", 900), ("LoanTerm", 0),
                             ("LoanTerm", 12.5), ("DTIRatio", float("nan")),
                             ("InterestRate", float("inf")), ("EmploymentType", "Unknown"),
                             ("HasCoSigner", "maybe"), ("Age", "bad")):
            with self.subTest(field=field):
                self.post("/api/loans", {"name": "Invalid", **COMPLETE_PROFILE, field: value}, 400)
        self.post("/api/loans", {"name": "Missing fields"}, 400)
        self.post("/api/loans", COMPLETE_PROFILE, 400)
        with database.get_connection() as conn:
            after = [conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("borrowers", "loans")]
        self.assertEqual(before, after)

    def test_malformed_json_and_non_object_rejected(self):
        for body in ("{", "[]", "null", '"hello"'):
            with self.subTest(body=body):
                response = self.fetch("/api/loans", method="POST", body=body)
                self.assertEqual(response.code, 400)
                self.assertIn("error", json.loads(response.body))

    def test_id_only_and_canonical_analysis_agree(self):
        loan = json.loads(self.fetch("/api/loans/LR-1054").body)
        canonical = validate_profile(loan)
        saved = self.post("/api/risk/analyze", {"loanId": loan["id"]})
        direct = self.post("/api/risk/analyze", canonical)
        for key in ("probability_of_default", "risk_score", "risk_level", "risk_drivers",
                    "protective_factors", "data_quality", "anomaly_indicators"):
            self.assertEqual(saved[key], direct[key], key)

    def test_unchanged_scenario_has_zero_delta(self):
        loan = json.loads(self.fetch("/api/loans/LR-1054").body)
        for scenario in ({}, validate_profile(loan), {"loanAmount": loan["loan_amount"],
                         "creditScore": loan["credit_score"], "dti": loan["dti_ratio"]}):
            result = self.post("/api/risk/simulate", {"baseLoanId": loan["id"], "scenario": scenario})
            self.assertEqual(result["comparison"], {"score_delta": 0, "pd_delta_pts": 0, "direction": "NO_CHANGE"})

    def test_scenario_aliases_override_and_zero_interest_is_valid(self):
        canonical = self.post("/api/risk/simulate", {"baseLoanId": "LR-1054",
            "scenario": {"LoanAmount": 60000, "LoanTerm": 12, "InterestRate": 0}})
        aliases = self.post("/api/risk/simulate", {"baseLoanId": "LR-1054",
            "scenario": {"loan_amount": 60000, "term": 12, "rate": 0}})
        self.assertEqual(canonical, aliases)
        self.assertEqual(aliases["scenario"]["indicative_emi"], 5000)

    def test_unknown_loans_and_invalid_scenarios_rejected(self):
        self.post("/api/risk/analyze", {"loanId": "missing"}, 404)
        self.post("/api/risk/simulate", {"baseLoanId": "missing"}, 404)
        self.post("/api/risk/simulate", {}, 400)
        self.post("/api/risk/simulate", {"baseLoanId": "LR-1054", "scenario": []}, 400)
        self.post("/api/risk/analyze", {"Income": 0}, 400)

    def test_queue_and_portfolio_use_one_latest_assessment(self):
        first = self.post("/api/risk/analyze", {"loanId": "LR-1054"})
        last = self.post("/api/risk/analyze", {"loanId": "LR-1054", **COMPLETE_PROFILE})
        self.assertNotEqual(first["risk_level"], last["risk_level"])
        # Force a timestamp tie to exercise the primary-key tie breaker.
        with database.get_connection() as conn:
            conn.execute("UPDATE risk_assessments SET assessed_at = '2026-01-01 00:00:00'")
        queue = json.loads(self.fetch("/api/loans").body)
        self.assertEqual(queue["count"], 6)
        self.assertEqual(len({loan["id"] for loan in queue["loans"]}), 6)
        row = next(loan for loan in queue["loans"] if loan["id"] == "LR-1054")
        self.assertEqual(row["risk_score"], last["risk_score"])
        detail = json.loads(self.fetch("/api/loans/LR-1054").body)
        self.assertEqual(detail["assessment"]["risk_score"], last["risk_score"])
        portfolio = json.loads(self.fetch("/api/exposure/portfolio").body)
        self.assertEqual(sum(portfolio["portfolio_summary"]["risk_distribution"].values()), 1)

    def test_incomplete_filter_selects_missing_and_contradictory_profiles(self):
        with database.get_connection() as conn:
            conn.execute("UPDATE loans SET credit_score = NULL WHERE id = 'LR-1048'")
            conn.execute("UPDATE borrowers SET age = 20, months_employed = 120 WHERE id = 'BRW-1051'")
        response = self.fetch("/api/loans?filter=incomplete")
        self.assertEqual(response.code, 200)
        ids = {loan["id"] for loan in json.loads(response.body)["loans"]}
        self.assertEqual(ids, {"LR-1048", "LR-1051"})
        self.assertEqual(self.fetch("/api/loans?filter=invalid").code, 400)

    def test_database_rolls_back_and_closes_connections(self):
        import sqlite3
        with self.assertRaises(RuntimeError):
            with database.get_connection() as conn:
                conn.execute("UPDATE loans SET credit_score = 300 WHERE id = 'LR-1054'")
                raise RuntimeError("force rollback")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
        with database.get_connection() as check:
            self.assertEqual(check.execute("SELECT credit_score FROM loans WHERE id = 'LR-1054'").fetchone()[0], 548)

    def test_analysis_does_not_reset_repaying_status(self):
        with database.get_connection() as conn:
            conn.execute("UPDATE loans SET status = 'REPAYING' WHERE id = 'LR-1054'")
        self.post("/api/risk/analyze", {"loanId": "LR-1054"})
        loan = json.loads(self.fetch("/api/loans/LR-1054").body)
        self.assertEqual(loan["status"], "REPAYING")

    def test_missing_required_saved_data_routes_to_verification(self):
        with database.get_connection() as conn:
            conn.execute("UPDATE loans SET credit_score = NULL WHERE id = 'LR-1054'")
        result = self.post("/api/risk/analyze", {"loanId": "LR-1054"})
        self.assertIn("CreditScore", result["data_quality"]["missing_required_fields"])
        loan = json.loads(self.fetch("/api/loans/LR-1054").body)
        self.assertEqual(loan["status"], "NEEDS_VERIFICATION")

    def test_explorer_literal_search_empty_results_valid_json(self):
        response = self.fetch("/api/dataset/explorer?search=%5B")
        self.assertEqual(response.code, 200)
        result = json.loads(response.body, parse_constant=lambda value: self.fail(value))
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["summary_stats"]["historical_default_rate"], 0)
        self.assertEqual(self.fetch("/api/dataset/explorer?page=invalid").code, 400)

    def test_removed_sample_is_not_a_fallback(self):
        with patch.object(DatasetExplorerHandler, "_df", None), patch("backend.server.DATA_PATH", self.test_db_path.parent / "missing.csv"):
            self.assertEqual(self.fetch("/api/dataset/explorer").code, 503)


class SchemaTests(unittest.TestCase):
    def test_aliases_preserve_zero_and_boolean_values(self):
        result = validate_profile({"dti_ratio": 0, "interest_rate": 0, "months_employed": 0,
                                   "num_credit_lines": 0, "has_cosigner": False})
        self.assertEqual(result, {"DTIRatio": 0, "InterestRate": 0, "MonthsEmployed": 0,
                                  "NumCreditLines": 0, "HasCoSigner": "No"})

    def test_conflicting_aliases_rejected(self):
        with self.assertRaises(ProfileValidationError):
            validate_profile({"CreditScore": 800, "credit_score": 400})

    def test_quality_invalid_values_do_not_crash_or_verify(self):
        for values in ({"Income": 0, "LoanAmount": 100000}, {"Age": "oops", "MonthsEmployed": 12},
                       {**COMPLETE_PROFILE, "CreditScore": float("inf")}):
            result = DataQualityEngine.evaluate(values)
            self.assertFalse(result["verification_ready"])
            self.assertTrue(result["validity_warnings"])

    def test_engines_accept_database_aliases(self):
        canonical = {"Income": 150000, "LoanAmount": 500000, "CreditScore": 420, "DTIRatio": .72,
                     "MonthsEmployed": 0, "Age": 65}
        aliases = {"income": 150000, "loan_amount": 500000, "credit_score": 420, "dti_ratio": .72,
                   "months_employed": 0, "age": 65}
        self.assertEqual(DataQualityEngine.evaluate(canonical), DataQualityEngine.evaluate(aliases))
        self.assertEqual(AnomalyDetector.evaluate(canonical), AnomalyDetector.evaluate(aliases))
        engine = RiskInferenceEngine.get_instance()
        self.assertEqual(engine.predict(canonical), engine.predict(aliases))


class StartupTests(unittest.TestCase):
    def test_each_required_artifact_is_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for missing in ARTIFACT_NAMES:
                for name in ARTIFACT_NAMES:
                    (root / name).write_bytes(b"" if name == missing else b"present")
                with self.assertRaisesRegex(FileNotFoundError, missing):
                    validate_artifact_files(root)

    def test_invalid_metrics_fail_loading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ARTIFACT_NAMES:
                (root / name).write_bytes((ARTIFACTS_DIR / name).read_bytes())
            (root / "model_metrics.json").write_text("{}", encoding="utf-8")
            with patch("ml.infer.ARTIFACTS_DIR", root), self.assertRaisesRegex(RuntimeError, "validated"):
                RiskInferenceEngine()

    def test_corrupted_artifacts_fail_loading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ARTIFACT_NAMES:
                (root / name).write_bytes(b"not a model artifact")
            with patch("ml.infer.ARTIFACTS_DIR", root), self.assertRaisesRegex(RuntimeError, "validated"):
                RiskInferenceEngine()

    def test_startup_failure_does_not_retrain_or_create_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "never-created.db"
            env = {**os.environ, "RISKORA_DB_PATH": str(path), "RISKORA_ARTIFACTS_DIR": str(root)}
            result = subprocess.run([sys.executable, "run.py", "--check"], cwd=PROJECT_ROOT,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Missing or empty model artifacts", result.stderr)
            self.assertEqual(list(root.iterdir()), [])

    def test_import_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "never-created.db"
            env = {**os.environ, "RISKORA_DB_PATH": str(path)}
            subprocess.run([sys.executable, "-c", "import backend.database; import backend.server"],
                           cwd=PROJECT_ROOT, env=env, check=True, capture_output=True)
            self.assertFalse(path.exists())

    def test_startup_check_does_not_write_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "never-created.db"
            env = {**os.environ, "RISKORA_DB_PATH": str(path)}
            result = subprocess.run([sys.executable, "run.py", "--check"], cwd=PROJECT_ROOT,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(path.exists())

    def test_fresh_server_starts_on_loopback(self):
        import socket
        import time
        from urllib.request import urlopen
        from urllib.error import URLError
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fresh.db"
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            env = {**os.environ, "RISKORA_DB_PATH": str(path), "RISKORA_HOST": "127.0.0.1",
                   "PYTHONUNBUFFERED": "1"}
            process = subprocess.Popen([sys.executable, "run.py", str(port)], cwd=PROJECT_ROOT,
                                       env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail(process.communicate()[1].decode(errors="replace"))
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/api/loans", timeout=1) as response:
                            payload = json.load(response)
                        break
                    except (URLError, TimeoutError):
                        time.sleep(0.1)
                else:
                    self.fail("Server did not start within 30 seconds.")
                self.assertEqual(payload["count"], 6)
                self.assertTrue(path.is_file())
            finally:
                process.terminate()
                process.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()

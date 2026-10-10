"""
RISKORA — Production-Style Backend Server & REST API Gateway
Powered by Tornado. Provides asynchronous REST APIs, real ML inference,
data quality scanning, anomaly detection, funding & repayment waterfalls,
relational persistence, and static frontend workstation delivery.
"""

import os
import sys
import json
import sqlite3
import datetime
import uuid
import time
import hashlib
from backend.security import session_user, authenticate, new_session, create_account
import numpy as np
import pandas as pd
import tornado.ioloop
import tornado.web

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import get_connection, init_db, seed_default_cases
from backend.config import PROJECT_ROOT, DATA_PATH, ARTIFACTS_DIR, HOST, PORT
from backend.schema import validate_profile, ProfileValidationError, inference_profile
from ml.infer import RiskInferenceEngine
from backend.services.data_quality import DataQualityEngine
from backend.services.anomaly_detector import AnomalyDetector
from backend.services.funding_service import FundingService
from backend.services.repayment_service import RepaymentService


def request_profile(raw, require_required=False):
    try:
        return validate_profile(raw, require_required=require_required)
    except ProfileValidationError as error:
        raise tornado.web.HTTPError(400, reason=str(error)) from error

# Same-origin JSON API utilities. Authentication is a later milestone.
class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("X-Content-Type-Options", "nosniff")
        self.set_header("Cache-Control", "no-store")
        self.set_header("X-Frame-Options", "DENY")

    def prepare(self):
        self.reviewer = session_user(self.get_cookie('riskora_session'))
        public = {'/api/health', '/api/auth/login', '/api/auth/setup'}
        if self.request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = self.request.headers.get('Origin')
            if origin and origin != f'{self.request.protocol}://{self.request.host}':
                raise tornado.web.HTTPError(403, reason='Cross-origin writes are not allowed.')
            if self.request.headers.get('X-Riskora-Request') != '1':
                raise tornado.web.HTTPError(403, reason='Missing request protection header.')
        if self.request.path not in public:
            if not self.reviewer:
                raise tornado.web.HTTPError(401, reason='Sign in to continue.')
            if self.request.method == 'POST' and self.request.path != '/api/auth/logout' and self.reviewer['role'] == 'VIEWER':
                raise tornado.web.HTTPError(403, reason='A reviewer role is required for this action.')

    def on_finish(self):
        if self.request.method == 'POST' and self.get_status() < 300 and getattr(self, 'reviewer', None):
            with get_connection() as conn:
                conn.execute('INSERT INTO audit_logs(event_type,entity_id,reviewer,details_json) VALUES (?,?,?,?)',
                    ('API_ACTION', self.request.path, str(self.reviewer['id']), json.dumps({'username':self.reviewer['username']})))

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def get_json_body(self):
        try:
            body = json.loads(self.request.body.decode("utf-8")) if self.request.body else {}
        except (ValueError, UnicodeError):
            raise tornado.web.HTTPError(400, reason="Request body must contain valid JSON.")
        if not isinstance(body, dict):
            raise tornado.web.HTTPError(400, reason="Request body must be a JSON object.")
        return body

    def write_json(self, data, status=200):
        self.set_status(status)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, indent=2, allow_nan=False))

    def write_error(self, status_code, **kwargs):
        self.set_header("Content-Type", "application/json")
        error_msg = "Internal Server Error"
        if status_code < 500:
            error_msg = self._reason
        self.finish(json.dumps({"error": error_msg, "status": status_code}))

# 1. Health & Status Handler
class HealthHandler(BaseHandler):
    def get(self):
        self.write_json({
            "status": "OPERATIONAL",
            "service": "RISKORA AI/ML Micro-Lending Risk Platform",
            "version": "1.0.0",
            "ml_engine": "Calibrated HistGradientBoosting v1.0",
            "database": "SQLite Persistent Relational Storage"
        })

# 2. Reviewer Auth Handler
class AuthHandler(BaseHandler):
    attempts = {}
    def post(self):
        data = self.get_json_body()
        username, password = data.get('username', ''), data.get('password', '')
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > 200:
            raise tornado.web.HTTPError(400, reason='Invalid credentials format.')
        now = time.monotonic()
        self.attempts = type(self).attempts
        for ip in list(self.attempts):
            self.attempts[ip] = [t for t in self.attempts[ip] if t > now-300]
            if not self.attempts[ip]: del self.attempts[ip]
        history = self.attempts.setdefault(self.request.remote_ip, [])
        if len(history) >= 10:
            raise tornado.web.HTTPError(429, reason='Too many sign-in attempts. Try again in five minutes.')
        history.append(now)
        user = authenticate(username, password)
        if not user:
            raise tornado.web.HTTPError(401, reason='Invalid username or password.')
        self.set_cookie('riskora_session', new_session(user['id']), httponly=True,
                        samesite='Strict', secure=self.request.protocol == 'https', max_age=28800)
        self.write_json({'user': {k:user[k] for k in ('id','username','role')}})

# 3. Loan Requests Queue Handler
class LoansHandler(BaseHandler):
    def get(self):
        search = self.get_argument("search", "").strip().lower()
        filter_status = self.get_argument("filter", "all").strip().lower()
        if filter_status not in {"all", "high", "analyzed", "incomplete"}:
            raise tornado.web.HTTPError(400, reason="Unknown loan filter.")
        
        with get_connection() as conn:
            cursor = conn.cursor()
            query = """
            SELECT l.id, l.loan_amount, l.credit_score, l.dti_ratio, l.num_credit_lines,
                   l.interest_rate, l.loan_term, l.loan_purpose, l.status, l.created_at,
                   b.name as borrower_name, b.age, b.income, b.employment_type, b.months_employed,
                   b.education, b.marital_status, b.has_cosigner, b.has_mortgage, b.has_dependents,
                   r.risk_score, r.probability_of_default, r.risk_level, r.data_quality_score, r.anomaly_detected
            FROM loans l
            JOIN borrowers b ON l.borrower_id = b.id
            LEFT JOIN risk_assessments r ON l.status != 'REQUEST_RECEIVED' AND r.id = (
                SELECT latest.id FROM risk_assessments latest WHERE latest.loan_id = l.id
                ORDER BY latest.assessed_at DESC, latest.id DESC LIMIT 1
            )
            ORDER BY l.created_at DESC, l.id DESC;
            """
            rows = cursor.execute(query).fetchall()
            
            results = []
            for r in rows:
                item = dict(r)
                # Apply search filter
                if search:
                    target = f"{item['id']} {item['borrower_name']} {item['loan_amount']} {item['loan_purpose']}".lower()
                    if search not in target:
                        continue
                        
                # Apply status filter
                if filter_status == "high" and item.get("risk_level") != "HIGH":
                    continue
                if filter_status == "analyzed" and not item.get("risk_level"):
                    continue
                if filter_status == "incomplete" and DataQualityEngine.evaluate(item)["verification_ready"]:
                    continue
                    
                results.append(item)
                
            self.write_json({"count": len(results), "loans": results})

    def post(self):
        data = self.get_json_body()
        name = data.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
            raise tornado.web.HTTPError(400, reason="Borrower name is required (1-200 characters).")
        name = name.strip()
        profile = request_profile(data, require_required=True)
        dq = DataQualityEngine.evaluate(profile)
        status = "REQUEST_RECEIVED" if dq["verification_ready"] else "NEEDS_VERIFICATION"
        
        with get_connection() as conn:
            cursor = conn.cursor()
            bid = f"BRW-{uuid.uuid4().hex}"
            lid = f"LR-{uuid.uuid4().hex}"
            
            cursor.execute("""
            INSERT INTO borrowers (id, name, age, income, education, employment_type,
                                   months_employed, marital_status, has_dependents, has_mortgage, has_cosigner)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (bid, name, profile.get("Age"), profile["Income"], profile.get("Education"),
                  profile.get("EmploymentType"), profile["MonthsEmployed"], profile.get("MaritalStatus"),
                  profile.get("HasDependents"), profile.get("HasMortgage"), profile.get("HasCoSigner")))
            
            cursor.execute("""
            INSERT INTO loans (id, borrower_id, loan_amount, credit_score, dti_ratio,
                               num_credit_lines, interest_rate, loan_term, loan_purpose, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (lid, bid, profile["LoanAmount"], profile["CreditScore"], profile["DTIRatio"],
                  profile["NumCreditLines"], profile["InterestRate"], profile["LoanTerm"],
                  profile.get("LoanPurpose"), status))
            
            conn.commit()
            
        self.write_json({"success": True, "loan_id": lid, "borrower_id": bid,
                         "status": status, "data_quality": dq}, status=201)

# 4. Single Loan Detail Handler
class LoanDetailHandler(BaseHandler):
    def get(self, loan_id):
        with get_connection() as conn:
            cursor = conn.cursor()
            query = """
            SELECT l.*, b.name as borrower_name, b.age, b.income, b.education,
                   b.employment_type, b.months_employed, b.marital_status,
                   b.has_dependents, b.has_mortgage, b.has_cosigner
            FROM loans l
            JOIN borrowers b ON l.borrower_id = b.id
            WHERE l.id = ?;
            """
            row = cursor.execute(query, (loan_id,)).fetchone()
            if not row:
                self.write_json({"error": f"Loan {loan_id} not found"}, status=404)
                return
                
            loan_data = dict(row)
            
            # Fetch latest assessment
            assessment_row = cursor.execute("""
            SELECT * FROM risk_assessments WHERE loan_id = ? ORDER BY assessed_at DESC, id DESC LIMIT 1;
            """, (loan_id,)).fetchone()
            
            if assessment_row and loan_data["status"] != "REQUEST_RECEIVED":
                ass_dict = dict(assessment_row)
                drivers = json.loads(ass_dict.get("drivers_json") or "[]")
                protective = json.loads(ass_dict.get("protective_json") or "[]")
                ass_dict["risk_drivers"] = drivers
                ass_dict["drivers"] = drivers
                ass_dict["protective_factors"] = protective
                ass_dict["protective"] = protective
                ass_dict["probability_pct"] = round(float(ass_dict.get("probability_of_default", 0.0)) * 100, 2)
                ass_dict["data_quality"] = json.loads(ass_dict.get("dq_details_json") or "{}")
                ass_dict["anomaly_indicators"] = json.loads(ass_dict.get("anomaly_details_json") or "{}")
                ass_dict["anomaly"] = ass_dict["anomaly_indicators"]
                ass_dict["recommended_action"] = "Human review required. " + ("Escalate to senior underwriter." if ass_dict["risk_level"] == "HIGH" else "Verify borrower documentation before a decision.")
                ass_dict["explainability_disclosure"] = "Policy rule indicators; these points are not trained-model feature attributions."
                loan_data["assessment"] = ass_dict
            else:
                loan_data["assessment"] = None

            # Fetch funding position
            funding_row = cursor.execute("""
            SELECT * FROM funding_positions WHERE loan_id = ? ORDER BY funded_at DESC, id DESC LIMIT 1;
            """, (loan_id,)).fetchone()
            if funding_row:
                fund_dict = dict(funding_row)
                fund_dict["positions"] = json.loads(fund_dict.get("positions_json") or "[]")
                positions = fund_dict["positions"]
                fund_dict.update(total_requested=round(sum(p["committed_amount"] for p in positions), 2),
                                 lender_count=len(positions),
                                 largest_lender_share=max((p["share_pct"] for p in positions), default=0),
                                 concentration_description=f"Saved allocation across {len(positions)} lenders.")
                loan_data["funding"] = fund_dict
            else:
                loan_data["funding"] = None

            # Fetch repayment schedule
            repay_row = cursor.execute("""
            SELECT * FROM repayment_schedules WHERE loan_id = ? ORDER BY created_at DESC, id DESC LIMIT 1;
            """, (loan_id,)).fetchone()
            if repay_row:
                rep_dict = dict(repay_row)
                rep_dict["installments"] = json.loads(rep_dict.get("installments_json") or "[]")
                rep_dict.update(original_principal=rep_dict["principal"],
                                annual_interest_rate=rep_dict["annual_rate"],
                                num_installments=len(rep_dict["installments"]),
                                allocation_policy_description=RepaymentService._get_policy_description(rep_dict["allocation_policy"]))
                summaries = {}
                for installment in rep_dict["installments"]:
                    for allocation in installment.get("allocations", []):
                        item = summaries.setdefault(allocation["lender_id"], dict(lender_id=allocation["lender_id"], lender_name=allocation["lender_name"], expected_principal=0, expected_interest=0, total_expected_return=0))
                        item["expected_principal"] += allocation["principal_allocated"]
                        item["expected_interest"] += allocation["interest_allocated"]
                        item["total_expected_return"] += allocation["total_allocated"]
                rep_dict["lender_summary"] = list(summaries.values())
                loan_data["repayment"] = rep_dict
            else:
                loan_data["repayment"] = None
                
            decision = cursor.execute('SELECT d.*,a.username FROM review_decisions d JOIN reviewer_accounts a ON a.id=d.reviewer_id WHERE loan_id=? ORDER BY d.id DESC LIMIT 1', (loan_id,)).fetchone()
            loan_data['review_decision'] = dict(decision) if decision else None
            from backend.services.payment_service import cents
            receipts = cursor.execute('SELECT * FROM payments WHERE loan_id=? ORDER BY id', (loan_id,)).fetchall()
            paid_by_lender = {}
            for receipt in receipts:
                for allocation in json.loads(receipt['allocations_json']):
                    lender = allocation['lender_id']
                    paid_by_lender[lender] = paid_by_lender.get(lender,0) + cents(allocation['principal_allocated'])
            committed = loan_data['funding']['total_requested'] if loan_data['funding'] else 0
            loan_data['ledger'] = {'received':sum(cents(r['amount_paid']) for r in receipts)/100,
                'principal_paid':sum(paid_by_lender.values())/100,
                'outstanding_principal':max(0,cents(committed)-sum(paid_by_lender.values()))/100,
                'lender_principal_paid':{k:v/100 for k,v in paid_by_lender.items()},
                'payment_count':len(receipts),
                'requires_reconciliation':any(r['schedule_id'] is None for r in receipts)}
            if loan_data['ledger']['requires_reconciliation']:
                loan_data['ledger']['outstanding_principal'] = None
                loan_data['ledger']['warning'] = 'Legacy payment records are not linked to schedule versions. Review the original receipts before relying on balances or recording further payments.'
            from backend.services.ora_service import build_brief
            loan_data['ora'] = build_brief(loan_data, dict(assessment_row)) if loan_data['assessment'] else None
            self.write_json(loan_data)

# 5. Risk Intelligence & ML Inference Handler
class RiskAnalysisHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        loan_id = data.get("loanId") or data.get("id")
        
        # Load loan profile from DB or request body
        loan_record = {}
        if loan_id:
            with get_connection() as conn:
                cursor = conn.cursor()
                row = cursor.execute("""
                SELECT l.*, b.age, b.income, b.education, b.employment_type,
                       b.months_employed, b.marital_status, b.has_dependents,
                       b.has_mortgage, b.has_cosigner
                FROM loans l
                JOIN borrowers b ON l.borrower_id = b.id
                WHERE l.id = ?;
                """, (loan_id,)).fetchone()
                if row:
                    loan_record = dict(row)
                else:
                    raise tornado.web.HTTPError(404, reason="Loan not found.")
                    
        # Overlay with any passed body fields
        combined = request_profile(loan_record) if loan_id else request_profile(data)
        if loan_id:
            overrides = request_profile(data)
            if any(combined.get(k) != v for k, v in overrides.items()):
                raise tornado.web.HTTPError(409, reason='Edit the borrower profile first, or use the scenario endpoint for hypothetical inputs.')
        
        # 1. Run Data Quality Engine
        dq_results = DataQualityEngine.evaluate(combined)
        
        # 2. Run Anomaly Detection Engine
        anomaly_results = AnomalyDetector.evaluate(combined)
        
        # 3. Run ML Inference Engine
        engine = RiskInferenceEngine.get_instance()
        ml_results = engine.predict(combined)
        
        # 4. Save Assessment to Database if loan_id exists
        if loan_id:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO risk_assessments (
                    loan_id, model_version, probability_of_default, risk_score,
                    risk_level, data_quality_score, anomaly_detected, review_level,
                    drivers_json, protective_json, dq_details_json, anomaly_details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    loan_id,
                    ml_results["model_metadata"]["version"],
                    ml_results["probability_of_default"],
                    ml_results["risk_score"],
                    ml_results["risk_level"],
                    dq_results["data_quality_score"],
                    1 if anomaly_results["anomaly_detected"] else 0,
                    ml_results["review_level"],
                    json.dumps(ml_results["risk_drivers"]),
                    json.dumps(ml_results["protective_factors"]),
                    json.dumps(dq_results),
                    json.dumps(anomaly_results)
                ))
                
                cursor.execute('UPDATE risk_assessments SET input_snapshot_json=?, reviewer_id=? WHERE id=?',
                    (json.dumps(combined), self.reviewer['id'], cursor.lastrowid))
                # Update loan status to RISK_ASSESSED
                cursor.execute("""UPDATE loans SET status = ? WHERE id = ?
                    AND status IN ('REQUEST_RECEIVED', 'NEEDS_VERIFICATION', 'RISK_ASSESSED', 'APPROVED', 'REJECTED');""",
                    ("RISK_ASSESSED" if dq_results["verification_ready"] else "NEEDS_VERIFICATION", loan_id))
                
                # Audit log
                cursor.execute("""
                INSERT INTO audit_logs (event_type, entity_id, reviewer, details_json)
                VALUES ('RISK_ANALYSIS_COMPLETED', ?, ?, ?);
                """, (loan_id, str(self.reviewer["id"]), json.dumps({"score": ml_results["risk_score"], "level": ml_results["risk_level"]})))
                
                conn.commit()

        response = {
            "loan_id": loan_id,
            "probability_of_default": ml_results["probability_of_default"],
            "probability_pct": ml_results["probability_pct"],
            "risk_score": ml_results["risk_score"],
            "risk_level": ml_results["risk_level"],
            "review_level": ml_results["review_level"],
            "recommended_action": ml_results["recommended_action"],
            "risk_drivers": ml_results["risk_drivers"],
            "protective_factors": ml_results["protective_factors"],
            "data_quality": dq_results,
            "anomaly_indicators": anomaly_results,
            "model_metadata": ml_results["model_metadata"],
            "explainability_disclosure": ml_results["explainability_disclosure"]
        }
        self.write_json(response)

# 6. What-If Scenario Lab Simulation Handler
class ScenarioSimulationHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        base_loan_id = data.get("baseLoanId")
        if not base_loan_id:
            raise tornado.web.HTTPError(400, reason="baseLoanId is required.")
        
        base_record = {}
        if base_loan_id:
            with get_connection() as conn:
                cursor = conn.cursor()
                row = cursor.execute("""
                SELECT l.*, b.age, b.income, b.education, b.employment_type,
                       b.months_employed, b.marital_status, b.has_dependents,
                       b.has_mortgage, b.has_cosigner
                FROM loans l
                JOIN borrowers b ON l.borrower_id = b.id
                WHERE l.id = ?;
                """, (base_loan_id,)).fetchone()
                if row:
                    base_record = dict(row)
                else:
                    raise tornado.web.HTTPError(404, reason="Base loan not found.")

        engine = RiskInferenceEngine.get_instance()
        
        # 1. Base prediction
        base_input = request_profile(base_record)
        base_res = engine.predict(base_input)
        
        # 2. Scenario prediction with modified parameters
        scenario_input = {**base_input, **request_profile(data.get("scenario", {}))}
        scenario_res = engine.predict(scenario_input)
        
        # Compute deltas
        score_delta = scenario_res["risk_score"] - base_res["risk_score"]
        pd_delta_pts = round((scenario_res["probability_of_default"] - base_res["probability_of_default"]) * 100, 2)
        
        # Indicative EMI for scenario
        normalized = inference_profile(scenario_input)
        sim_amt, sim_term = normalized["LoanAmount"], normalized["LoanTerm"]
        sim_rate = normalized["InterestRate"] / 1200.0
        emi = sim_amt / sim_term if sim_rate == 0 else sim_amt * sim_rate * ((1 + sim_rate) ** sim_term) / (((1 + sim_rate) ** sim_term) - 1)
        
        self.write_json({
            "base": {
                "score": base_res["risk_score"],
                "pd_pct": base_res["probability_pct"],
                "level": base_res["risk_level"]
            },
            "scenario": {
                "score": scenario_res["risk_score"],
                "pd_pct": scenario_res["probability_pct"],
                "level": scenario_res["risk_level"],
                "indicative_emi": round(emi, 2),
                "recommended_mode": "fractional" if scenario_res["risk_level"] == "HIGH" or sim_amt > 75000 else "single"
            },
            "comparison": {
                "score_delta": score_delta,
                "pd_delta_pts": pd_delta_pts,
                "direction": "INCREASED_RISK" if score_delta > 0 else ("DECREASED_RISK" if score_delta < 0 else "NO_CHANGE")
            },
            "simulation_notice": "SIMULATION ONLY: Hypothetical what-if recalculation. Results do not modify saved loan request."
        })

# 7. Funding Optimization & Commitment Handler
class FundingHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        loan_id = data.get("loanId")
        amount = request_profile({"LoanAmount":data.get("amount",120000)})["LoanAmount"]
        if amount is None: raise tornado.web.HTTPError(400, reason="Funding amount is required.")
        risk_level = data.get("riskLevel", "MEDIUM")
        mode = data.get("mode", "auto")
        raw_count = data.get('lenderCount',3)
        if isinstance(raw_count,bool) or not isinstance(raw_count,(int,float)) or not np.isfinite(raw_count) or int(raw_count) != raw_count:
            raise tornado.web.HTTPError(400, reason='Lender count must be a whole number.')
        lender_count = int(raw_count)
        
        if not np.isfinite(amount) or amount <= 0 or mode not in ("auto", "single", "fractional"):
            raise tornado.web.HTTPError(400, reason="Provide a positive amount and valid funding mode.")
        if not 2 <= lender_count <= 6:
            raise tornado.web.HTTPError(400, reason='Lender pool size must be between 2 and 6 (single mode uses one lender).')
        if loan_id:
            with get_connection() as conn:
                loan = conn.execute('SELECT * FROM loans WHERE id=?', (loan_id,)).fetchone()
                if not loan: raise tornado.web.HTTPError(404, reason='Loan not found.')
                if loan['status'] != 'APPROVED':
                    raise tornado.web.HTTPError(409, reason='An explicit reviewer approval is required before funding. Existing commitments cannot be overwritten.')
                if round(amount,2) != round(loan['loan_amount'],2):
                    raise tornado.web.HTTPError(409, reason='Funding must equal the approved loan amount.')
                assessment = conn.execute('SELECT risk_level FROM risk_assessments WHERE loan_id=? ORDER BY id DESC LIMIT 1', (loan_id,)).fetchone()
                risk_level = assessment['risk_level']
        funding_result = FundingService.calculate_structure(
            loan_amount=amount,
            risk_level=risk_level,
            mode=mode,
            lender_count=lender_count
        )
        
        if loan_id:
            with get_connection() as conn:
                if not conn.execute("SELECT id FROM loans WHERE id = ?", (loan_id,)).fetchone():
                    raise tornado.web.HTTPError(404, reason="Loan not found.")
                if conn.execute("SELECT id FROM payments WHERE loan_id = ? LIMIT 1", (loan_id,)).fetchone():
                    raise tornado.web.HTTPError(409, reason="A loan with recorded payments cannot be reconfigured.")
        # Save funding position if loan_id provided
        if loan_id:
            with get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                if conn.execute('SELECT status FROM loans WHERE id=?', (loan_id,)).fetchone()['status'] != 'APPROVED':
                    raise tornado.web.HTTPError(409, reason='Loan status changed. Reload before funding.')
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO funding_positions (loan_id, mode, herfindahl_index, concentration_rating, positions_json)
                VALUES (?, ?, ?, ?, ?);
                """, (
                    loan_id,
                    funding_result["mode"],
                    funding_result["herfindahl_index"],
                    funding_result["concentration_rating"],
                    json.dumps(funding_result["positions"])
                ))
                cursor.execute("UPDATE loans SET status = 'FUNDED' WHERE id = ?;", (loan_id,))
                cursor.execute('INSERT INTO audit_logs(event_type,entity_id,reviewer,details_json) VALUES (?,?,?,?)',
                    ('FUNDING_COMMITTED',loan_id,str(self.reviewer['id']),json.dumps(funding_result)))
                conn.commit()

        self.write_json(funding_result)

# 8. Repayment Schedule & Execution Handler
class RepaymentHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        loan_id = data.get("loanId")
        values = request_profile({'LoanAmount':data.get('principal',120000), 'InterestRate':data.get('rate',12), 'LoanTerm':data.get('term',36)})
        principal, annual_rate, term = values['LoanAmount'], values['InterestRate'], values['LoanTerm']
        if any(v is None for v in values.values()): raise tornado.web.HTTPError(400, reason='Provide principal, rate and term.')
        if not loan_id: raise tornado.web.HTTPError(400, reason='A saved funded loan is required.')
        start_date = data.get("startDate")
        if start_date is not None:
            try: datetime.date.fromisoformat(start_date)
            except (ValueError,TypeError): raise tornado.web.HTTPError(400, reason='First due date must be a valid YYYY-MM-DD date.')
        schedule_type = data.get("scheduleType", "monthly")
        policy = data.get("allocationPolicy", "pro-rata")
        positions = data.get("positions", [])
        
        if loan_id:
            with get_connection() as conn:
                if not conn.execute("SELECT id FROM loans WHERE id = ?", (loan_id,)).fetchone():
                    raise tornado.web.HTTPError(404, reason="Loan not found.")
                if conn.execute("SELECT id FROM payments WHERE loan_id = ? LIMIT 1", (loan_id,)).fetchone():
                    raise tornado.web.HTTPError(409, reason="A loan with recorded payments cannot be reconfigured.")
        if loan_id:
            with get_connection() as conn:
                loan = conn.execute('SELECT * FROM loans WHERE id=?', (loan_id,)).fetchone()
                fund = conn.execute('SELECT * FROM funding_positions WHERE loan_id=? ORDER BY id DESC LIMIT 1', (loan_id,)).fetchone()
                if not fund or loan['status'] not in ('FUNDED', 'REPAYMENT_CONFIGURED'):
                    raise tornado.web.HTTPError(409, reason='Commit approved funding before generating a schedule.')
                if principal != loan['loan_amount'] or annual_rate != loan['interest_rate'] or term != loan['loan_term']:
                    raise tornado.web.HTTPError(409, reason='Schedule terms must match the approved loan. Edit terms before approval.')
                positions = json.loads(fund['positions_json'])
        if not np.isfinite(principal) or principal <= 0 or not np.isfinite(annual_rate) or not 0 <= annual_rate <= 100 or not 1 <= term <= 600:
            raise tornado.web.HTTPError(400, reason="Invalid principal, annual rate or term.")
        if schedule_type not in ("monthly", "bi-monthly", "flexible") or policy not in ("pro-rata", "largest-first", "earliest-first"):
            raise tornado.web.HTTPError(400, reason="Invalid schedule type or allocation policy.")
        if positions and round(sum(p["committed_amount"] for p in positions), 2) != round(principal, 2):
            raise tornado.web.HTTPError(400, reason="Lender commitments must equal the schedule principal.")
        schedule = RepaymentService.generate_schedule(
            principal=principal,
            annual_rate_pct=annual_rate,
            term_months=term,
            start_date_str=start_date,
            schedule_type=schedule_type,
            allocation_policy=policy,
            lender_positions=positions
        )
        
        if loan_id:
            with get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                if conn.execute('SELECT 1 FROM payments WHERE loan_id=?', (loan_id,)).fetchone():
                    raise tornado.web.HTTPError(409, reason='Payments exist; the schedule cannot be replaced.')
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO repayment_schedules (
                    loan_id, schedule_type, allocation_policy, principal,
                    annual_rate, term_months, indicative_emi, total_interest,
                    total_repayable, installments_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    loan_id,
                    schedule["schedule_type"],
                    schedule["allocation_policy"],
                    schedule["original_principal"],
                    schedule["annual_interest_rate"],
                    schedule["term_months"],
                    schedule["indicative_emi"],
                    schedule["total_interest"],
                    schedule["total_repayable"],
                    json.dumps(schedule["installments"])
                ))
                schedule["id"] = cursor.lastrowid
                cursor.execute("UPDATE loans SET status = 'REPAYMENT_CONFIGURED' WHERE id = ?;", (loan_id,))
                conn.commit()
                
        self.write_json(schedule)

# 9. Payment Event Recording Handler
class RecordPaymentHandler(BaseHandler):
    def post(self):
        from backend.services.payment_service import apply_payment, cents
        data = self.get_json_body()
        loan_id = data.get('loanId') or data.get('loan_id')
        inst_num = data.get('installmentNum')
        key = data.get('idempotencyKey')
        if not isinstance(inst_num,int) or isinstance(inst_num,bool) or not isinstance(key,str) or not 8 <= len(key) <= 100:
            raise tornado.web.HTTPError(400, reason='Installment number and a unique payment reference (8–100 characters) are required.')
        try:
            amount = cents(data.get('amount'))/100
        except ValueError as error:
            raise tornado.web.HTTPError(400, reason=str(error))
        with get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            previous = conn.execute('SELECT * FROM payments WHERE idempotency_key=?', (key,)).fetchone()
            if previous:
                if previous['loan_id'] != loan_id or previous['installment_num'] != inst_num or previous['amount_paid'] != amount:
                    raise tornado.web.HTTPError(409, reason='This payment reference was already used for a different payment.')
                self.write_json({'success':True,'duplicate':True,'payment_id':previous['id']})
                return
            if conn.execute('SELECT 1 FROM payments WHERE loan_id=? AND schedule_id IS NULL', (loan_id,)).fetchone():
                raise tornado.web.HTTPError(409, reason='Legacy receipts require reconciliation before additional payments.')
            sched = conn.execute('SELECT * FROM repayment_schedules WHERE loan_id=? ORDER BY id DESC LIMIT 1', (loan_id,)).fetchone()
            if not sched: raise tornado.web.HTTPError(409, reason='Generate a schedule before recording payments.')
            if data.get('scheduleId') != sched['id']:
                raise tornado.web.HTTPError(409, reason='Schedule changed. Reload the case before recording payment.')
            installments = json.loads(sched['installments_json'])
            target = next((i for i in installments if i['installment_num']==inst_num), None)
            if not target: raise tornado.web.HTTPError(404, reason='Installment not found.')
            if target['status'] == 'PAID': raise tornado.web.HTTPError(409, reason='Installment already paid.')
            try: allocations = apply_payment(target,amount)
            except ValueError as error: raise tornado.web.HTTPError(400, reason=str(error))
            target['paid_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor = conn.execute('INSERT INTO payments(loan_id,installment_num,amount_paid,allocations_json,schedule_id,idempotency_key) VALUES (?,?,?,?,?,?)',
                (loan_id,inst_num,amount,json.dumps(allocations),sched['id'],key))
            payment_id = cursor.lastrowid
            conn.execute('UPDATE repayment_schedules SET installments_json=? WHERE id=?', (json.dumps(installments),sched['id']))
            status = 'CLOSED' if all(i['status']=='PAID' for i in installments) else 'REPAYING'
            conn.execute('UPDATE loans SET status=? WHERE id=?', (status,loan_id))
            conn.execute('INSERT INTO audit_logs(event_type,entity_id,reviewer,details_json) VALUES (?,?,?,?)',
                ('PAYMENT_RECORDED',loan_id,str(self.reviewer['id']),json.dumps({'payment_id':payment_id,'amount':amount,'schedule_id':sched['id'],'reference':key})))
        self.write_json({'success':True,'payment':target,'payment_id':payment_id,'loan_status':status})

# 10. Lender Portfolio Exposure Monitor Handler
class PortfolioExposureHandler(BaseHandler):
    def get(self):
        with get_connection() as conn:
            cursor = conn.cursor()
            
            total_loans = cursor.execute("SELECT COUNT(*) FROM loans;").fetchone()[0]
            total_req = cursor.execute("SELECT SUM(loan_amount) FROM loans;").fetchone()[0] or 0.0
            
            # Risk band breakdowns
            band_rows = cursor.execute("""
            SELECT r.risk_level, COUNT(*) as count, AVG(r.risk_score) as avg_score, AVG(r.probability_of_default) as avg_pd
            FROM risk_assessments r
            WHERE r.id = (SELECT latest.id FROM risk_assessments latest
                WHERE latest.loan_id = r.loan_id
                ORDER BY latest.assessed_at DESC, latest.id DESC LIMIT 1)
            GROUP BY r.risk_level;
            """).fetchall()
            
            bands = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
            for r in band_rows:
                if r["risk_level"]:
                    bands[r["risk_level"]] = r["count"]

            # Active funding positions
            positions = cursor.execute("""
            SELECT f.*, l.loan_amount, b.name as borrower_name
            FROM funding_positions f
            JOIN loans l ON f.loan_id = l.id
            JOIN borrowers b ON l.borrower_id = b.id
            WHERE f.id = (SELECT MAX(latest.id) FROM funding_positions latest WHERE latest.loan_id=f.loan_id)
            ORDER BY f.funded_at DESC LIMIT 10;
            """).fetchall()
            
            active_pos = []
            for p in positions:
                item = dict(p)
                item["positions"] = json.loads(item.get("positions_json") or "[]")
                active_pos.append(item)
                
            self.write_json({
                "portfolio_summary": {
                    "total_loans_evaluated": total_loans,
                    "total_portfolio_principal": round(total_req, 2),
                    "risk_distribution": bands,
                    "high_risk_exposure_pct": round((bands.get("HIGH", 0) / max(total_loans, 1)) * 100, 1),
                    "active_lender_pools": cursor.execute("SELECT COUNT(DISTINCT loan_id) FROM funding_positions").fetchone()[0]
                },
                "recent_funding_structures": active_pos
            })

# 11. Dataset Explorer Handler (Server-Side Paginated & Filtered)
class DatasetExplorerHandler(BaseHandler):
    _df = None
    
    @classmethod
    def get_df(cls):
        if cls._df is None:
            if not DATA_PATH.is_file():
                raise tornado.web.HTTPError(503, reason="Benchmark dataset is unavailable.")
            cls._df = pd.read_csv(DATA_PATH)
        return cls._df

    def get(self):
        df = self.get_df()
        search = self.get_argument("search", "").strip().lower()
        risk_filter = self.get_argument("risk", "all").strip().capitalize()
        sort_by = self.get_argument("sort", "score")
        try:
            page = max(1, int(self.get_argument("page", 1)))
            limit = max(10, min(100, int(self.get_argument("limit", 25))))
        except ValueError:
            raise tornado.web.HTTPError(400, reason="page and limit must be integers.")
        
        filtered = df.copy()
        
        # Search by LoanID or Purpose or Education
        if search:
            mask = (
                filtered["LoanID"].astype(str).str.lower().str.contains(search, regex=False) |
                filtered["Income"].astype(str).str.contains(search, regex=False) |
                filtered["CreditScore"].astype(str).str.contains(search, regex=False)
            )
            filtered = filtered[mask]
            
        # Target isolation check: Default is historical validation, not feature
        if "Default" in filtered.columns and not filtered.empty:
            historical_default_rate = round(float(filtered["Default"].mean() * 100), 2)
        else:
            historical_default_rate = 0.0

        # Fast approximate scoring for dataset view using empirical model weights
        filtered["EstPD"] = np.clip(
            1.0 / (1.0 + np.exp(
                - (-1.60 - 0.0095 * (filtered["CreditScore"] - 620) + 3.20 * (filtered["DTIRatio"] - 0.36) + 1.85 * (filtered["LoanAmount"] / filtered["Income"] - 0.32))
            )),
            0.01, 0.95
        )
        filtered["Score"] = np.clip(np.round(np.where(
            filtered["EstPD"] < 0.08, (filtered["EstPD"] / 0.08) * 30,
            np.where(filtered["EstPD"] < 0.20, 30 + ((filtered["EstPD"] - 0.08) / 0.12) * 30, 60 + ((filtered["EstPD"] - 0.20) / 0.40) * 39)
        )), 0, 99).astype(int)
        
        filtered["RiskLevel"] = np.where(
            filtered["EstPD"] >= 0.20, "High",
            np.where(filtered["EstPD"] >= 0.08, "Medium", "Low")
        )
        
        if risk_filter in ["High", "Medium", "Low"]:
            filtered = filtered[filtered["RiskLevel"] == risk_filter]

        # Sorting
        if sort_by == "loan":
            filtered = filtered.sort_values("LoanAmount", ascending=False)
        elif sort_by == "credit":
            filtered = filtered.sort_values("CreditScore", ascending=False)
        elif sort_by == "income":
            filtered = filtered.sort_values("Income", ascending=False)
        else:
            filtered = filtered.sort_values("Score", ascending=False)
            
        total_records = len(filtered)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        page_df = filtered.iloc[start_idx:end_idx]
        
        records = []
        for _, row in page_df.iterrows():
            records.append({
                "LoanID": str(row["LoanID"]),
                "Income": int(row["Income"]),
                "LoanAmount": int(row["LoanAmount"]),
                "CreditScore": int(row["CreditScore"]),
                "DTIRatio": round(float(row["DTIRatio"]), 2),
                "MonthsEmployed": int(row.get("MonthsEmployed", 24)),
                "InterestRate": round(float(row.get("InterestRate", 12.0)), 1),
                "LoanTerm": int(row.get("LoanTerm", 36)),
                "Score": int(row["Score"]),
                "RiskLevel": str(row["RiskLevel"]),
                "ProbabilityDefault": round(float(row["EstPD"]), 4),
                "Default": int(row.get("Default", 0))
            })
            
        counts = df["Default"].value_counts().to_dict() if "Default" in df.columns else {}
        
        self.write_json({
            "pagination": {
                "page": page,
                "limit": limit,
                "total_records": total_records,
                "total_pages": (total_records + limit - 1) // limit
            },
            "summary_stats": {
                "dataset_size": len(df),
                "historical_default_rate": historical_default_rate,
                "avg_credit_score": round(float(df["CreditScore"].mean()), 1),
                "avg_loan_amount": round(float(df["LoanAmount"].mean()), 0),
                "target_isolated": True
            },
            "rows": records
        })

# 12. Model Metrics & Live Performance Handler
class ModelMetricsHandler(BaseHandler):
    def get(self):
        metrics_path = ARTIFACTS_DIR / "model_metrics.json"
        if os.path.exists(metrics_path):
            with open(metrics_path, "r") as f:
                data = json.load(f)
            self.write_json(data)
        else:
            self.write_json({"error": "Model metrics not generated. Please run ml/train.py."}, status=404)

# 13. Application Factory & Server Startup
class PublicFileHandler(tornado.web.StaticFileHandler):
    """Allow only frontend entry files and the bundled public asset directory."""
    def set_extra_headers(self, path):
        self.set_header("Cache-Control", "no-cache")

    async def get(self, path, include_body=True):
        await super().get(path or "index.html", include_body=include_body)

    def validate_absolute_path(self, root, absolute_path):
        from pathlib import Path
        resolved = Path(absolute_path).resolve()
        try:
            relative = resolved.relative_to(PROJECT_ROOT)
        except ValueError:
            raise tornado.web.HTTPError(404)
        public_files = {"index.html", "app.js", "integration.js", "styles.css"}
        if relative.as_posix() not in public_files:
            if len(relative.parts) != 2 or relative.parts[0] != "assets" or relative.suffix.lower() not in {".png", ".mp4"}:
                raise tornado.web.HTTPError(404)
        return super().validate_absolute_path(root, absolute_path)


def make_app():
    static_path = str(PROJECT_ROOT)
    
    from backend.integration import integration_routes
    return tornado.web.Application(integration_routes() + [
        # REST API Routes
        (r"/api/health", HealthHandler),
        (r"/api/auth/login", AuthHandler),
        (r"/api/loans", LoansHandler),
        (r"/api/loans/([^/]+)", LoanDetailHandler),
        (r"/api/risk/analyze", RiskAnalysisHandler),
        (r"/api/risk/simulate", ScenarioSimulationHandler),
        (r"/api/funding/optimize", FundingHandler),
        (r"/api/repayment/generate", RepaymentHandler),
        (r"/api/repayment/record", RecordPaymentHandler),
        (r"/api/exposure/portfolio", PortfolioExposureHandler),
        (r"/api/dataset/explorer", DatasetExplorerHandler),
        (r"/api/model/metrics", ModelMetricsHandler),
        
        # Static Workstation Assets & Fallback
        (r"/(.*)", PublicFileHandler, {
            "path": static_path,
            "default_filename": "index.html"
        }),
    ], debug=False)

def run_server(port=PORT):
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")
    # Pre-load ML engine
    RiskInferenceEngine.get_instance()
    init_db()
    seed_default_cases()
    
    app = make_app()
    bound = False
    original_port = port
    
    for p in range(port, min(port + 10, 65536)):
        try:
            app.listen(p, address=HOST)
            port = p
            bound = True
            break
        except OSError as e:
            if getattr(e, 'winerror', None) == 10048 or getattr(e, 'errno', None) == 98:
                continue
            raise

    if not bound:
        print(f"[ERROR] Could not bind to any port between {original_port} and {original_port + 9}. Please check running processes.")
        return

    print(f"=" * 68)
    print(f"  RISKORA — Institutional Risk Intelligence Workstation")
    print(f"  Server running live at: http://localhost:{port}")
    if port != original_port:
        print(f"  (Note: Port {original_port} was in use; switched to port {port})")
    print(f"  REST API Gateway:       http://localhost:{port}/api/health")
    print(f"  Model Engine:           Calibrated HistGradientBoosting v1.0")
    print(f"  Database Storage:       SQLite persistent layer (riskora.db)")
    print(f"=" * 68)
    try:
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] RISKORA Server stopped gracefully.")

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)


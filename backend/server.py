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
import numpy as np
import pandas as pd
import tornado.ioloop
import tornado.web

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import get_connection, init_db, seed_default_cases
from ml.infer import RiskInferenceEngine
from backend.services.data_quality import DataQualityEngine
from backend.services.anomaly_detector import AnomalyDetector
from backend.services.funding_service import FundingService
from backend.services.repayment_service import RepaymentService

# Base Handler with JSON utilities and CORS support
class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def get_json_body(self):
        try:
            return json.loads(self.request.body.decode("utf-8")) if self.request.body else {}
        except Exception:
            return {}

    def write_json(self, data, status=200):
        self.set_status(status)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, indent=2))

    def write_error(self, status_code, **kwargs):
        self.set_header("Content-Type", "application/json")
        exc_info = kwargs.get("exc_info")
        error_msg = "Internal Server Error"
        if exc_info and len(exc_info) > 1 and exc_info[1]:
            error_msg = str(exc_info[1])
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
    def post(self):
        data = self.get_json_body()
        reviewer_name = data.get("name", "").strip() or "Senior Underwriter"
        with get_connection() as conn:
            cursor = conn.cursor()
            user_id = f"USR-{abs(hash(reviewer_name)) % 10000:04d}"
            cursor.execute("""
            INSERT INTO users (id, username, full_name, role)
            VALUES (?, ?, ?, 'RISK_UNDERWRITER')
            ON CONFLICT(username) DO UPDATE SET full_name = excluded.full_name;
            """, (user_id, reviewer_name.lower().replace(" ", "_"), reviewer_name))
            conn.commit()
            
        self.write_json({
            "success": True,
            "user": {
                "id": user_id,
                "name": reviewer_name,
                "role": "CHIEF_RISK_ANALYST",
                "session_active": True
            }
        })

# 3. Loan Requests Queue Handler
class LoansHandler(BaseHandler):
    def get(self):
        search = self.get_argument("search", "").strip().lower()
        filter_status = self.get_argument("filter", "all").strip().lower()
        
        with get_connection() as conn:
            cursor = conn.cursor()
            query = """
            SELECT l.id, l.loan_amount, l.credit_score, l.dti_ratio, l.num_credit_lines,
                   l.interest_rate, l.loan_term, l.loan_purpose, l.status, l.created_at,
                   b.name as borrower_name, b.income, b.employment_type, b.months_employed,
                   b.education, b.has_cosigner, b.has_mortgage, b.has_dependents,
                   r.risk_score, r.probability_of_default, r.risk_level, r.data_quality_score, r.anomaly_detected
            FROM loans l
            JOIN borrowers b ON l.borrower_id = b.id
            LEFT JOIN risk_assessments r ON l.id = r.loan_id
            ORDER BY l.created_at DESC;
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
                if filter_status == "incomplete" and (item.get("income") is None or item.get("credit_score") is None or item.get("data_quality_score", 100) < 70):
                    continue
                    
                results.append(item)
                
            self.write_json({"count": len(results), "loans": results})

    def post(self):
        data = self.get_json_body()
        name = data.get("name", "").strip() or "Anonymous Borrower"
        income = float(data.get("income", 300000))
        loan_amount = float(data.get("loanAmount", 100000))
        credit_score = int(data.get("creditScore", 650))
        dti = float(data.get("dti", 0.30))
        term = int(data.get("term", 36))
        purpose = data.get("purpose", "General Micro-Enterprise")
        emp_type = data.get("employmentType", "Salaried")
        months_emp = int(data.get("monthsEmployed", 24))
        
        with get_connection() as conn:
            cursor = conn.cursor()
            bid = f"BRW-{datetime.datetime.now().strftime('%M%S%f')[:7]}"
            lid = f"LR-{datetime.datetime.now().strftime('%M%S%f')[:6]}"
            
            cursor.execute("""
            INSERT INTO borrowers (id, name, income, education, employment_type, months_employed)
            VALUES (?, ?, ?, 'Bachelor\'s', ?, ?);
            """, (bid, name, income, emp_type, months_emp))
            
            cursor.execute("""
            INSERT INTO loans (id, borrower_id, loan_amount, credit_score, dti_ratio, loan_term, loan_purpose, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'REQUEST_RECEIVED');
            """, (lid, bid, loan_amount, credit_score, dti, term, purpose))
            
            conn.commit()
            
        self.write_json({"success": True, "loan_id": lid, "borrower_id": bid})

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
            SELECT * FROM risk_assessments WHERE loan_id = ? ORDER BY assessed_at DESC LIMIT 1;
            """, (loan_id,)).fetchone()
            
            if assessment_row:
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
                loan_data["assessment"] = ass_dict
            else:
                loan_data["assessment"] = None

            # Fetch funding position
            funding_row = cursor.execute("""
            SELECT * FROM funding_positions WHERE loan_id = ? ORDER BY funded_at DESC LIMIT 1;
            """, (loan_id,)).fetchone()
            if funding_row:
                fund_dict = dict(funding_row)
                fund_dict["positions"] = json.loads(fund_dict.get("positions_json") or "[]")
                loan_data["funding"] = fund_dict
            else:
                loan_data["funding"] = None

            # Fetch repayment schedule
            repay_row = cursor.execute("""
            SELECT * FROM repayment_schedules WHERE loan_id = ? ORDER BY created_at DESC LIMIT 1;
            """, (loan_id,)).fetchone()
            if repay_row:
                rep_dict = dict(repay_row)
                rep_dict["installments"] = json.loads(rep_dict.get("installments_json") or "[]")
                loan_data["repayment"] = rep_dict
            else:
                loan_data["repayment"] = None
                
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
                    
        # Overlay with any passed body fields
        combined = {**loan_record, **data}
        
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
                
                # Update loan status to RISK_ASSESSED
                cursor.execute("UPDATE loans SET status = 'RISK_ASSESSED' WHERE id = ?;", (loan_id,))
                
                # Audit log
                cursor.execute("""
                INSERT INTO audit_logs (event_type, entity_id, reviewer, details_json)
                VALUES ('RISK_ANALYSIS_COMPLETED', ?, 'Underwriter', ?);
                """, (loan_id, json.dumps({"score": ml_results["risk_score"], "level": ml_results["risk_level"]})))
                
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

        engine = RiskInferenceEngine.get_instance()
        
        # 1. Base prediction
        base_input = {**base_record}
        base_res = engine.predict(base_input)
        
        # 2. Scenario prediction with modified parameters
        scenario_input = {**base_record, **data.get("scenario", {})}
        scenario_res = engine.predict(scenario_input)
        
        # Compute deltas
        score_delta = scenario_res["risk_score"] - base_res["risk_score"]
        pd_delta_pts = round((scenario_res["probability_of_default"] - base_res["probability_of_default"]) * 100, 2)
        
        # Indicative EMI for scenario
        sim_amt = float(scenario_input.get("LoanAmount", scenario_input.get("loan_amount", 120000)))
        sim_term = int(scenario_input.get("LoanTerm", scenario_input.get("loan_term", 36)))
        sim_rate = 0.12 / 12.0
        emi = sim_amt * sim_rate * ((1 + sim_rate) ** sim_term) / (((1 + sim_rate) ** sim_term) - 1)
        
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
        amount = float(data.get("amount", 120000))
        risk_level = data.get("riskLevel", "MEDIUM")
        mode = data.get("mode", "auto")
        lender_count = int(data.get("lenderCount", 3))
        
        funding_result = FundingService.calculate_structure(
            loan_amount=amount,
            risk_level=risk_level,
            mode=mode,
            lender_count=lender_count
        )
        
        # Save funding position if loan_id provided
        if loan_id:
            with get_connection() as conn:
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
                cursor.execute("UPDATE loans SET status = 'FUNDING_OPTIMIZED' WHERE id = ?;", (loan_id,))
                conn.commit()

        self.write_json(funding_result)

# 8. Repayment Schedule & Execution Handler
class RepaymentHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        loan_id = data.get("loanId")
        principal = float(data.get("principal", 120000))
        annual_rate = float(data.get("rate", 12.0))
        term = int(data.get("term", 36))
        start_date = data.get("startDate")
        schedule_type = data.get("scheduleType", "monthly")
        policy = data.get("allocationPolicy", "pro-rata")
        positions = data.get("positions", [])
        
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
                cursor.execute("UPDATE loans SET status = 'REPAYMENT_CONFIGURED' WHERE id = ?;", (loan_id,))
                conn.commit()
                
        self.write_json(schedule)

# 9. Payment Event Recording Handler
class RecordPaymentHandler(BaseHandler):
    def post(self):
        try:
            data = self.get_json_body()
            loan_id = data.get("loanId") or data.get("loan_id") or data.get("id")
            inst_num = int(data.get("installmentNum") or data.get("installment_num") or 1)
            amount = float(data.get("amount", 0.0))
            
            if not loan_id:
                self.write_json({"error": "Loan ID required"}, status=400)
                return
                
            with get_connection() as conn:
                cursor = conn.cursor()
                sched_row = cursor.execute("""
                SELECT * FROM repayment_schedules WHERE loan_id = ? ORDER BY created_at DESC LIMIT 1;
                """, (loan_id,)).fetchone()
                
                # Resilient fallback: If no schedule exists yet, auto-generate the baseline plan
                if not sched_row:
                    loan_row = cursor.execute("SELECT * FROM loans WHERE id = ?;", (loan_id,)).fetchone()
                    if not loan_row:
                        self.write_json({"error": f"Loan {loan_id} not found"}, status=404)
                        return
                    
                    # Fetch funding positions if any
                    fund_row = cursor.execute("SELECT * FROM funding_positions WHERE loan_id = ? ORDER BY funded_at DESC LIMIT 1;", (loan_id,)).fetchone()
                    positions = json.loads(fund_row["positions_json"]) if fund_row else None
                    
                    gen_schedule = RepaymentService.generate_schedule(
                        principal=float(loan_row["loan_amount"]),
                        annual_rate_pct=float(loan_row["interest_rate"]),
                        term_months=int(loan_row["loan_term"]),
                        schedule_type="monthly",
                        allocation_policy="pro-rata",
                        lender_positions=positions
                    )
                    cursor.execute("""
                    INSERT INTO repayment_schedules (
                        loan_id, schedule_type, allocation_policy, principal,
                        annual_rate, term_months, indicative_emi, total_interest,
                        total_repayable, installments_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        loan_id,
                        gen_schedule["schedule_type"],
                        gen_schedule["allocation_policy"],
                        gen_schedule["original_principal"],
                        gen_schedule["annual_interest_rate"],
                        gen_schedule["term_months"],
                        gen_schedule["indicative_emi"],
                        gen_schedule["total_interest"],
                        gen_schedule["total_repayable"],
                        json.dumps(gen_schedule["installments"])
                    ))
                    conn.commit()
                    sched_row = cursor.execute("""
                    SELECT * FROM repayment_schedules WHERE loan_id = ? ORDER BY created_at DESC LIMIT 1;
                    """, (loan_id,)).fetchone()
                    
                installments = json.loads(sched_row["installments_json"])
                target = next((inst for inst in installments if inst.get("installment_num") == inst_num), None)
                if not target:
                    self.write_json({"error": f"Installment #{inst_num} not found in schedule"}, status=404)
                    return
                    
                target["status"] = "PAID"
                target["paid_at"] = datetime.datetime.now().isoformat()
                target["actual_amount_paid"] = amount or target.get("payment_amount", 0.0)
                allocations = target.get("allocations") or []
                
                cursor.execute("""
                INSERT INTO payments (loan_id, installment_num, amount_paid, allocations_json)
                VALUES (?, ?, ?, ?);
                """, (loan_id, inst_num, target["actual_amount_paid"], json.dumps(allocations)))
                
                # Update installments in schedule
                cursor.execute("""
                UPDATE repayment_schedules SET installments_json = ? WHERE id = ?;
                """, (json.dumps(installments), sched_row["id"]))
                
                # Institutional Audit Log entry
                cursor.execute("""
                INSERT INTO audit_logs (event_type, entity_id, reviewer, details_json)
                VALUES (?, ?, ?, ?);
                """, (
                    "PAYMENT_RECORDED",
                    loan_id,
                    "Institutional Risk Desk",
                    json.dumps({
                        "installment_num": inst_num,
                        "amount_paid": target["actual_amount_paid"],
                        "paid_at": target["paid_at"],
                        "remaining_balance": target.get("remaining_balance", 0.0)
                    })
                ))
                
                # Check if entire loan is settled
                unpaid = [i for i in installments if i.get("status") != "PAID"]
                new_loan_status = "FULLY_PAID" if len(unpaid) == 0 else "REPAYING"
                cursor.execute("UPDATE loans SET status = ? WHERE id = ?;", (new_loan_status, loan_id))
                
                conn.commit()
                
            self.write_json({
                "success": True,
                "message": f"Installment #{inst_num} recorded as PAID.",
                "payment": target,
                "loan_status": new_loan_status,
                "unpaid_count": len(unpaid)
            })
        except Exception as e:
            self.write_json({"error": f"Failed to record payment: {str(e)}"}, status=500)

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
                    "active_lender_pools": 6
                },
                "recent_funding_structures": active_pos
            })

# 11. Dataset Explorer Handler (Server-Side Paginated & Filtered)
class DatasetExplorerHandler(BaseHandler):
    _df = None
    
    @classmethod
    def get_df(cls):
        if cls._df is None:
            csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "loan_default_full.csv")
            if os.path.exists(csv_path):
                cls._df = pd.read_csv(csv_path)
            else:
                sample_path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_loan_default.csv")
                cls._df = pd.read_csv(sample_path)
        return cls._df

    def get(self):
        df = self.get_df()
        search = self.get_argument("search", "").strip().lower()
        risk_filter = self.get_argument("risk", "all").strip().capitalize()
        sort_by = self.get_argument("sort", "score")
        page = max(1, int(self.get_argument("page", 1)))
        limit = max(10, min(100, int(self.get_argument("limit", 25))))
        
        filtered = df.copy()
        
        # Search by LoanID or Purpose or Education
        if search:
            mask = (
                filtered["LoanID"].astype(str).str.lower().str.contains(search) |
                filtered["Income"].astype(str).str.contains(search) |
                filtered["CreditScore"].astype(str).str.contains(search)
            )
            filtered = filtered[mask]
            
        # Target isolation check: Default is historical validation, not feature
        if "Default" in filtered.columns:
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
        filtered["Score"] = np.round(np.where(
            filtered["EstPD"] < 0.08, (filtered["EstPD"] / 0.08) * 30,
            np.where(filtered["EstPD"] < 0.20, 30 + ((filtered["EstPD"] - 0.08) / 0.12) * 30, 60 + ((filtered["EstPD"] - 0.20) / 0.40) * 39)
        )).astype(int)
        
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
        metrics_path = os.path.join(os.path.dirname(__file__), "..", "ml", "artifacts", "model_metrics.json")
        if os.path.exists(metrics_path):
            with open(metrics_path, "r") as f:
                data = json.load(f)
            self.write_json(data)
        else:
            self.write_json({"error": "Model metrics not generated. Please run ml/train.py."}, status=404)

# 13. Application Factory & Server Startup
def make_app():
    static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    return tornado.web.Application([
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
        (r"/(.*)", tornado.web.StaticFileHandler, {
            "path": static_path,
            "default_filename": "index.html"
        }),
    ], debug=False)

def run_server(port=8000):
    init_db()
    seed_default_cases()
    # Pre-load ML engine
    RiskInferenceEngine.get_instance()
    
    app = make_app()
    bound = False
    original_port = port
    
    for p in range(port, port + 10):
        try:
            app.listen(p)
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


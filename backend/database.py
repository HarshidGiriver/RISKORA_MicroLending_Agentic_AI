"""
RISKORA — Relational Database Layer (SQLite)
Provides persistent storage, schema migrations, and relational integrity for:
Users, Borrowers, Loans, Risk Assessments, Funding, Repayments, and Audit Logs.
"""

import os
import sqlite3
import json
import datetime
from contextlib import contextmanager
from backend.config import DB_PATH as CONFIG_DB_PATH
from typing import Dict, Any, List, Optional

DB_PATH = str(CONFIG_DB_PATH)

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def init_db():
    """Initializes schema and tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Users / Reviewers table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'RISK_UNDERWRITER',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 2. Borrowers table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS borrowers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            income REAL NOT NULL,
            education TEXT,
            employment_type TEXT,
            months_employed INTEGER,
            marital_status TEXT,
            has_dependents TEXT DEFAULT 'No',
            has_mortgage TEXT DEFAULT 'No',
            has_cosigner TEXT DEFAULT 'No',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 3. Loans table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            id TEXT PRIMARY KEY,
            borrower_id TEXT NOT NULL,
            loan_amount REAL NOT NULL,
            credit_score INTEGER,
            dti_ratio REAL,
            num_credit_lines INTEGER,
            interest_rate REAL,
            loan_term INTEGER,
            loan_purpose TEXT,
            status TEXT DEFAULT 'REQUEST_RECEIVED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (borrower_id) REFERENCES borrowers(id) ON DELETE CASCADE
        );
        """)
        
        # 4. Risk Assessments table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id TEXT NOT NULL,
            model_version TEXT NOT NULL,
            probability_of_default REAL NOT NULL,
            risk_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            data_quality_score INTEGER NOT NULL,
            anomaly_detected INTEGER NOT NULL DEFAULT 0,
            review_level TEXT NOT NULL,
            drivers_json TEXT,
            protective_json TEXT,
            dq_details_json TEXT,
            anomaly_details_json TEXT,
            assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (loan_id) REFERENCES loans(id) ON DELETE CASCADE
        );
        """)
        
        # 5. Funding Positions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS funding_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            herfindahl_index REAL,
            concentration_rating TEXT,
            positions_json TEXT NOT NULL,
            funded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (loan_id) REFERENCES loans(id) ON DELETE CASCADE
        );
        """)
        
        # 6. Repayment Schedules table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS repayment_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id TEXT NOT NULL,
            schedule_type TEXT NOT NULL,
            allocation_policy TEXT NOT NULL,
            principal REAL NOT NULL,
            annual_rate REAL NOT NULL,
            term_months INTEGER NOT NULL,
            indicative_emi REAL NOT NULL,
            total_interest REAL NOT NULL,
            total_repayable REAL NOT NULL,
            installments_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (loan_id) REFERENCES loans(id) ON DELETE CASCADE
        );
        """)
        
        # 7. Payment Events table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id TEXT NOT NULL,
            installment_num INTEGER NOT NULL,
            amount_paid REAL NOT NULL,
            paid_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            allocations_json TEXT NOT NULL,
            FOREIGN KEY (loan_id) REFERENCES loans(id) ON DELETE CASCADE
        );
        """)
        
        # 8. Audit Logs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            entity_id TEXT,
            reviewer TEXT,
            details_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        conn.commit()

def seed_default_cases():
    """Seeds realistic loan requests to demonstrate all risk bands and workflows."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if already seeded
        cursor.execute("SELECT COUNT(*) FROM loans;")
        if cursor.fetchone()[0] > 0:
            return  # Already populated
            
        default_users = [
            ("USR-101", "reviewer_1", "Senior Underwriting Officer", "CHIEF_RISK_ANALYST")
        ]
        cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP);", default_users)
        
        # 6 Curated Cases with diverse credit & risk attributes
        cases = [
            {
                "bid": "BRW-1054", "name": "Rahul P", "age": 29, "income": 280000,
                "education": "High School", "emp_type": "Contract", "months_emp": 8,
                "marital": "Single", "dependents": "Yes", "mortgage": "No", "cosigner": "No",
                "lid": "LR-1054", "amount": 120000, "credit": 548, "dti": 0.52,
                "lines": 9, "rate": 18.5, "term": 36, "purpose": "Business"
            },
            {
                "bid": "BRW-1048", "name": "Arun Kumar", "age": 42, "income": 580000,
                "education": "Bachelor's", "emp_type": "Salaried", "months_emp": 60,
                "marital": "Married", "dependents": "Yes", "mortgage": "Yes", "cosigner": "Yes",
                "lid": "LR-1048", "amount": 75000, "credit": 734, "dti": 0.22,
                "lines": 4, "rate": 11.0, "term": 24, "purpose": "Home"
            },
            {
                "bid": "BRW-1051", "name": "Meena S", "age": 35, "income": 360000,
                "education": "Bachelor's", "emp_type": "Self-employed", "months_emp": 24,
                "marital": "Married", "dependents": "Yes", "mortgage": "No", "cosigner": "No",
                "lid": "LR-1051", "amount": 95000, "credit": 618, "dti": 0.38,
                "lines": 6, "rate": 14.5, "term": 36, "purpose": "Auto"
            },
            {
                "bid": "BRW-1057", "name": "Divya R", "age": 31, "income": 490000,
                "education": "Master's", "emp_type": "Salaried", "months_emp": 36,
                "marital": "Single", "dependents": "No", "mortgage": "Yes", "cosigner": "No",
                "lid": "LR-1057", "amount": 60000, "credit": 698, "dti": 0.26,
                "lines": 3, "rate": 12.0, "term": 18, "purpose": "Education"
            },
            {
                "bid": "BRW-1060", "name": "Karthik M (Incomplete)", "age": 26, "income": 240000,
                "education": "High School", "emp_type": "Self-employed", "months_emp": 10,
                "marital": "Single", "dependents": "No", "mortgage": "No", "cosigner": "No",
                "lid": "LR-1060", "amount": 90000, "credit": 505, "dti": 0.58,
                "lines": 8, "rate": 19.5, "term": 48, "purpose": "Business"
            },
            {
                "bid": "BRW-1063", "name": "Priya N", "age": 38, "income": 720000,
                "education": "Master's", "emp_type": "Salaried", "months_emp": 72,
                "marital": "Married", "dependents": "Yes", "mortgage": "Yes", "cosigner": "Yes",
                "lid": "LR-1063", "amount": 40000, "credit": 782, "dti": 0.16,
                "lines": 2, "rate": 9.5, "term": 12, "purpose": "Education"
            }
        ]
        
        for c in cases:
            cursor.execute("""
            INSERT INTO borrowers (id, name, age, income, education, employment_type, months_employed, marital_status, has_dependents, has_mortgage, has_cosigner)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (c["bid"], c["name"], c["age"], c["income"], c["education"], c["emp_type"], c["months_emp"], c["marital"], c["dependents"], c["mortgage"], c["cosigner"]))
            
            cursor.execute("""
            INSERT INTO loans (id, borrower_id, loan_amount, credit_score, dti_ratio, num_credit_lines, interest_rate, loan_term, loan_purpose, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'REQUEST_RECEIVED');
            """, (c["lid"], c["bid"], c["amount"], c["credit"], c["dti"], c["lines"], c["rate"], c["term"], c["purpose"]))
            
        conn.commit()

# Initialization is explicit at startup or in an isolated test fixture.

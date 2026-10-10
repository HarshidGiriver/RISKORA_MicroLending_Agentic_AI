"""OraAgent-inspired application, review and account features on the existing API."""
import hashlib
import json
import sqlite3
import tornado.web
from backend.database import get_connection
from backend.security import hash_password, create_account
from backend.schema import validate_profile, ProfileValidationError, NUMERIC, CATEGORIES, REQUIRED


def integration_routes():
    from backend.server import BaseHandler

    class Setup(BaseHandler):
        def get(self):
            with get_connection() as conn:
                available = not conn.execute('SELECT 1 FROM reviewer_accounts LIMIT 1').fetchone()
            self.write_json({'setup_required': available})

        def post(self):
            if self.request.remote_ip not in ('127.0.0.1', '::1'):
                raise tornado.web.HTTPError(403, reason='Initial account setup is available only on this computer.')
            data = self.get_json_body()
            username, password = data.get('username'), data.get('password')
            if not isinstance(username, str) or not 3 <= len(username.strip()) <= 80 or not isinstance(password, str) or not 12 <= len(password) <= 200:
                raise tornado.web.HTTPError(400, reason='Use a username of 3–80 characters and a password of 12–200 characters.')
            salt, digest = hash_password(password)
            with get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                if conn.execute('SELECT 1 FROM reviewer_accounts LIMIT 1').fetchone():
                    raise tornado.web.HTTPError(409, reason='Setup is complete. Sign in with your account.')
                conn.execute('INSERT INTO reviewer_accounts(username,salt,password_hash,role) VALUES (?,?,?,?)',
                             (username.strip().lower(), salt, digest, 'ADMIN'))
            self.write_json({'success': True}, 201)

    class Me(BaseHandler):
        def get(self): self.write_json({'user': self.reviewer})

    class Logout(BaseHandler):
        def post(self):
            with get_connection() as conn:
                conn.execute('DELETE FROM reviewer_sessions WHERE token_hash=?',
                             (hashlib.sha256(self.get_cookie('riskora_session', '').encode()).hexdigest(),))
            self.clear_cookie('riskora_session')
            self.write_json({'success': True})

    class Accounts(BaseHandler):
        def post(self):
            if self.reviewer['role'] != 'ADMIN':
                raise tornado.web.HTTPError(403, reason='An administrator account is required.')
            data = self.get_json_body()
            try: create_account(data.get('username'), data.get('password'), data.get('role', 'REVIEWER'))
            except ValueError as error: raise tornado.web.HTTPError(400, reason=str(error))
            except sqlite3.IntegrityError: raise tornado.web.HTTPError(409, reason='Username already exists.')
            self.write_json({'success': True}, 201)

    class Schema(BaseHandler):
        def get(self): self.write_json({'numeric': NUMERIC, 'categories': CATEGORIES, 'required': REQUIRED})

    class Edit(BaseHandler):
        def post(self, loan_id):
            data = self.get_json_body()
            try: profile = validate_profile(data, require_required=True)
            except ProfileValidationError as error: raise tornado.web.HTTPError(400, reason=str(error))
            name = data.get('name')
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
                raise tornado.web.HTTPError(400, reason='Borrower name is required (1–200 characters).')
            with get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                loan = conn.execute('SELECT * FROM loans WHERE id=?', (loan_id,)).fetchone()
                if not loan: raise tornado.web.HTTPError(404, reason='Loan not found.')
                if conn.execute('SELECT 1 FROM funding_positions WHERE loan_id=?', (loan_id,)).fetchone():
                    raise tornado.web.HTTPError(409, reason='A funded loan cannot be edited.')
                borrower_map = {'age':'Age','income':'Income','education':'Education','employment_type':'EmploymentType',
                    'months_employed':'MonthsEmployed','marital_status':'MaritalStatus','has_dependents':'HasDependents','has_mortgage':'HasMortgage','has_cosigner':'HasCoSigner'}
                loan_map = {'loan_amount':'LoanAmount','credit_score':'CreditScore','dti_ratio':'DTIRatio','num_credit_lines':'NumCreditLines',
                    'interest_rate':'InterestRate','loan_term':'LoanTerm','loan_purpose':'LoanPurpose'}
                conn.execute('UPDATE borrowers SET name=?, '+','.join(k+'=?' for k in borrower_map)+' WHERE id=?',
                    [name.strip()]+[profile.get(v) for v in borrower_map.values()]+[loan['borrower_id']])
                conn.execute("UPDATE loans SET status='REQUEST_RECEIVED', "+','.join(k+'=?' for k in loan_map)+' WHERE id=?',
                    [profile.get(v) for v in loan_map.values()]+[loan_id])
                conn.execute('INSERT INTO audit_logs(event_type,entity_id,reviewer,details_json) VALUES (?,?,?,?)',
                    ('PROFILE_UPDATED',loan_id,str(self.reviewer['id']),json.dumps(profile)))
            self.write_json({'success': True, 'id':loan_id})

    class Review(BaseHandler):
        def post(self, loan_id):
            data = self.get_json_body()
            decision, note = data.get('decision'), data.get('note')
            if decision not in ('APPROVED','REJECTED','NEEDS_VERIFICATION') or not isinstance(note,str) or not 5 <= len(note.strip()) <= 2000:
                raise tornado.web.HTTPError(400, reason='Choose a decision and enter a review note (5–2000 characters).')
            with get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                loan = conn.execute('SELECT * FROM loans WHERE id=?', (loan_id,)).fetchone()
                if not loan: raise tornado.web.HTTPError(404, reason='Loan not found.')
                if loan['status'] not in ('RISK_ASSESSED','NEEDS_VERIFICATION'):
                    raise tornado.web.HTTPError(409, reason='Assess the current saved profile before recording a decision.')
                assessment = conn.execute('SELECT * FROM risk_assessments WHERE loan_id=? ORDER BY id DESC LIMIT 1', (loan_id,)).fetchone()
                if not assessment or data.get('assessment_id') != assessment['id']:
                    raise tornado.web.HTTPError(409, reason='Assessment changed. Reload the case before reviewing.')
                if decision == 'APPROVED' and not json.loads(assessment['dq_details_json']).get('verification_ready'):
                    raise tornado.web.HTTPError(409, reason='Resolve input quality issues and reassess before approval.')
                conn.execute('INSERT INTO review_decisions(loan_id,assessment_id,decision,note,reviewer_id) VALUES (?,?,?,?,?)',
                    (loan_id,assessment['id'],decision,note.strip(),self.reviewer['id']))
                conn.execute('UPDATE loans SET status=? WHERE id=?', (decision,loan_id))
            self.write_json({'success':True, 'status':decision})

    class Audit(BaseHandler):
        def get(self, loan_id):
            with get_connection() as conn:
                rows = conn.execute('SELECT id,event_type,reviewer,details_json,created_at FROM audit_logs WHERE entity_id=? ORDER BY id DESC LIMIT 100', (loan_id,)).fetchall()
                decisions = conn.execute('SELECT d.decision,d.note,d.created_at,a.username FROM review_decisions d JOIN reviewer_accounts a ON a.id=d.reviewer_id WHERE loan_id=? ORDER BY d.id DESC', (loan_id,)).fetchall()
            self.write_json({'events':[dict(r) for r in rows], 'decisions':[dict(r) for r in decisions]})

    return [(r'/api/auth/setup',Setup),(r'/api/auth/me',Me),(r'/api/auth/logout',Logout),
            (r'/api/auth/accounts',Accounts),(r'/api/schema',Schema),(r'/api/loans/([^/]+)/edit',Edit),
            (r'/api/loans/([^/]+)/review',Review),(r'/api/loans/([^/]+)/audit',Audit)]

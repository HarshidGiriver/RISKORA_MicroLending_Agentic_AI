import json
import hashlib
import shutil
from pathlib import Path
from unittest.mock import patch
import unittest
from tornado.testing import AsyncHTTPTestCase
from backend.server import make_app, AuthHandler
from backend.database import get_connection, init_db
from backend.security import new_session
from backend.services.payment_service import cents
from tests.support import IsolatedDatabaseMixin, _TEST_PASSWORD
from tests.test_foundation import COMPLETE_PROFILE


class OraIntegrationTests(IsolatedDatabaseMixin, AsyncHTTPTestCase):
    def get_app(self): return make_app()
    def get_test_timeout(self): return 30
    def post(self,path,body,status=200,**kwargs):
        response = self.fetch(path,method='POST',body=json.dumps(body),**kwargs)
        self.assertEqual(response.code,status,response.body.decode())
        return json.loads(response.body)
    def detail(self): return json.loads(self.fetch('/api/loans/LR-1054').body)

    def test_authentication_logout_and_csrf(self):
        for path in ('/api/loans','/api/model/metrics','/api/exposure/portfolio','/api/auth/me'):
            self.assertEqual(self.fetch(path,headers={'Cookie':''}).code,401)
        AuthHandler.attempts.clear()
        self.post('/api/auth/login',{'username':'test-reviewer','password':'wrong password'},401)
        response = self.fetch('/api/auth/login',method='POST',body=json.dumps({'username':'test-reviewer','password':'test-reviewer-password'}))
        self.assertEqual(response.code,200)
        self.assertIn('HttpOnly',response.headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',response.headers['Set-Cookie'])
        self.post('/api/loans',{},403,headers={'Origin':'https://other.invalid'})
        self.post('/api/loans',{},403,headers={'X-Riskora-Request':''})
        self.post('/api/auth/logout',{})
        self.assertEqual(self.fetch('/api/loans').code,401)

    def test_roles_and_expired_sessions(self):
        with get_connection() as conn:
            conn.execute('INSERT INTO reviewer_accounts(id,username,salt,password_hash,role) VALUES (2,?,?,?,?)',('viewer',*_TEST_PASSWORD,'VIEWER'))
        token = new_session(2)
        headers = {'Cookie':f'riskora_session={token}'}
        self.assertEqual(self.fetch('/api/loans',headers=headers).code,200)
        self.post('/api/risk/analyze',{'loanId':'LR-1054'},403,headers=headers)
        self.post('/api/auth/accounts',{'username':'new-reviewer','password':'another-long-password'},403,headers=headers)
        with get_connection() as conn: conn.execute('UPDATE reviewer_sessions SET expires_at=0')
        self.assertEqual(self.fetch('/api/loans').code,401)

    def test_first_account_setup_is_one_time(self):
        self.post('/api/auth/setup',{'username':'admin','password':'some-long-password'},409)
        with get_connection() as conn:
            conn.execute('DELETE FROM reviewer_sessions')
            conn.execute('DELETE FROM reviewer_accounts')
        self.post('/api/auth/setup',{'username':'admin','password':'short'},400)
        self.post('/api/auth/setup',{'username':'admin','password':'some-long-password'},201)
        self.post('/api/auth/setup',{'username':'other','password':'some-long-password'},409)

    def test_approval_snapshot_and_ora_truthfulness(self):
        self.post('/api/funding/optimize',{'loanId':'LR-1054','amount':120000},409)
        self.approve_seed()
        detail = self.detail()
        self.assertEqual(detail['status'],'APPROVED')
        self.assertEqual(detail['ora']['risk_level'],detail['assessment']['risk_level'])
        self.assertEqual(detail['ora']['evidence'][0]['value'],COMPLETE_PROFILE['Income'])
        self.assertNotIn('Certified Genuine',json.dumps(detail['ora']))
        self.assertEqual(detail['assessment']['reviewer_id'],1)
        self.post('/api/risk/analyze',{'loanId':'LR-1054','CreditScore':300},409)
        self.post('/api/risk/analyze',{'loanId':'LR-1054'})
        self.post('/api/funding/optimize',{'loanId':'LR-1054','amount':120000},409)
        self.post('/api/loans/LR-1054/review',{'decision':'APPROVED','note':'Reviewed documents','assessment_id':detail['assessment']['id']},409)

    def test_input_edit_requires_reassessment(self):
        self.approve_seed()
        old_id = self.detail()['assessment']['id']
        self.post('/api/loans/LR-1054/edit',{'name':'Updated',**COMPLETE_PROFILE})
        self.assertEqual(self.detail()['status'],'REQUEST_RECEIVED')
        self.assertIsNone(self.detail()['assessment'])
        self.post('/api/loans/LR-1054/review',{'decision':'APPROVED','note':'Try obsolete assessment','assessment_id':old_id},409)

    def test_partial_payment_idempotency_and_exact_allocations(self):
        self.fund_seed(rate=0,term=12)
        plan = self.post('/api/repayment/generate',{'loanId':'LR-1054','principal':120000,'rate':0,'term':12})
        request = dict(loanId='LR-1054',scheduleId=plan['id'],installmentNum=1,amount=3333.33,idempotencyKey='receipt-partial-1')
        self.post('/api/repayment/record',{**request,'scheduleId':-1},409)
        result = self.post('/api/repayment/record',request)
        self.assertEqual(result['payment']['status'],'PARTIAL')
        self.assertEqual(cents(result['payment']['principal_paid']),333333)
        self.assertEqual(cents(self.detail()['ledger']['outstanding_principal']),11666667)
        self.assertTrue(self.post('/api/repayment/record',request)['duplicate'])
        self.post('/api/repayment/record',{**request,'amount':1},409)
        self.post('/api/repayment/record',{**request,'amount':0.001,'idempotencyKey':'receipt-invalid'},400)
        result = self.post('/api/repayment/record',{**request,'amount':6666.67,'idempotencyKey':'receipt-partial-2'})
        self.assertEqual(result['payment']['status'],'PAID')
        self.assertEqual(cents(result['payment']['principal_paid']),1000000)
        with get_connection() as conn:
            rows = conn.execute('SELECT * FROM payments').fetchall()
            self.assertEqual(len(rows),2)
            for row in rows:
                allocations = json.loads(row['allocations_json'])
                self.assertEqual(cents(row['amount_paid']),sum(cents(a['total_allocated']) for a in allocations))
                self.assertEqual(row['schedule_id'],plan['id'])
            self.assertEqual(conn.execute("SELECT reviewer FROM audit_logs WHERE event_type='PAYMENT_RECORDED' LIMIT 1").fetchone()[0],'1')
        self.post('/api/risk/analyze',{'loanId':'LR-1054'})
        self.assertEqual(self.detail()['status'],'REPAYING')
        self.post('/api/loans/LR-1054/edit',{'name':'Changed',**COMPLETE_PROFILE},409)
        self.post('/api/repayment/generate',{'loanId':'LR-1054'},409)

    def test_schedule_version_and_approved_terms(self):
        self.fund_seed(rate=0,term=12)
        self.post('/api/repayment/generate',{'loanId':'LR-1054','principal':120000,'rate':99,'term':12},409)
        body = {'loanId':'LR-1054','principal':120000,'rate':0,'term':12}
        first = self.post('/api/repayment/generate',body)
        second = self.post('/api/repayment/generate',body)
        self.assertNotEqual(first['id'],second['id'])
        self.post('/api/repayment/record',{'loanId':'LR-1054','installmentNum':1,'scheduleId':first['id'],'amount':1,'idempotencyKey':'obsolete-plan'},409)


    def test_incomplete_input_cannot_be_approved(self):
        profile = {**COMPLETE_PROFILE, 'Education':None}
        self.post('/api/loans/LR-1054/edit',{'name':'Incomplete',**profile})
        result = self.post('/api/risk/analyze',{'loanId':'LR-1054'})
        self.assertFalse(result['data_quality']['verification_ready'])
        detail = self.detail()
        self.assertEqual(detail['status'],'NEEDS_VERIFICATION')
        self.post('/api/loans/LR-1054/review',{'decision':'APPROVED','note':'Cannot skip missing input','assessment_id':detail['assessment']['id']},409)

    def test_final_payment_closes_loan_and_zeroes_ledger(self):
        self.fund_seed(rate=0,term=1)
        plan = self.post('/api/repayment/generate',{'loanId':'LR-1054','principal':120000,'rate':0,'term':1})
        self.post('/api/repayment/record',{'loanId':'LR-1054','scheduleId':plan['id'],'installmentNum':1,'amount':120000,'idempotencyKey':'final-receipt'})
        detail = self.detail()
        self.assertEqual(detail['status'],'CLOSED')
        self.assertEqual(detail['ledger']['outstanding_principal'],0)
        self.post('/api/risk/analyze',{'loanId':'LR-1054'})
        self.assertEqual(self.detail()['status'],'CLOSED')

    def test_malformed_financial_values_are_client_errors(self):
        for amount in ('bad', True, None, 1.111):
            self.post('/api/funding/optimize',{'amount':amount},400)
        for count in (None, 'bad', 2.5, True, 0, 21):
            self.post('/api/funding/optimize',{'amount':100,'lenderCount':count},400)
        self.post('/api/repayment/generate',{'loanId':'LR-1054','term':1.1},400)
        self.post('/api/repayment/generate',{'loanId':'LR-1054','startDate':'bad'},400)

    def test_legacy_receipts_are_preserved_and_flagged(self):
        self.fund_seed(rate=0,term=12)
        plan = self.post('/api/repayment/generate',{'loanId':'LR-1054','principal':120000,'rate':0,'term':12})
        with get_connection() as conn:
            conn.execute('INSERT INTO payments(loan_id,installment_num,amount_paid,allocations_json) VALUES (?,?,?,?)',
                ('LR-1054',1,10000,json.dumps(plan['installments'][0]['allocations'])))
        init_db()
        detail = self.detail()
        self.assertTrue(detail['ledger']['requires_reconciliation'])
        self.assertIsNone(detail['ledger']['outstanding_principal'])
        self.assertEqual(detail['ledger']['payment_count'],1)
        self.post('/api/repayment/record',{'loanId':'LR-1054','scheduleId':plan['id'],'installmentNum':2,'amount':10000,'idempotencyKey':'legacy-block'},409)

    def test_default_migration_copies_legacy_without_modifying_it(self):
        from backend import database
        root = self.test_db_path.parent / 'migration'
        (root / 'data').mkdir(parents=True)
        legacy = root / 'data' / 'riskora.db'
        runtime = root / 'data' / 'runtime' / 'riskora.db'
        shutil.copyfile(self.test_db_path,legacy)
        before = hashlib.sha256(legacy.read_bytes()).hexdigest()
        with patch.object(database,'PROJECT_ROOT',root), patch.object(database,'DB_PATH',str(runtime)):
            init_db()
            with get_connection() as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM loans').fetchone()[0],6)
        self.assertTrue(runtime.is_file())
        self.assertEqual(before,hashlib.sha256(legacy.read_bytes()).hexdigest())

    def test_additive_migration_preserves_rows(self):
        with get_connection() as conn:
            before = [tuple(r) for r in conn.execute('SELECT * FROM loans ORDER BY id')]
        init_db(); init_db()
        with get_connection() as conn:
            self.assertEqual(before,[tuple(r) for r in conn.execute('SELECT * FROM loans ORDER BY id')])

if __name__ == '__main__': unittest.main()

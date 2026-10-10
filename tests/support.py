"""Fresh SQLite database per test, never the configured application database."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from backend import database
import json
from backend.security import hash_password, new_session
_TEST_PASSWORD = hash_password("test-reviewer-password")


class IsolatedDatabaseMixin:
    def setUp(self):
        temporary = TemporaryDirectory(prefix="riskora-test-")
        self.addCleanup(temporary.cleanup)
        self.test_db_path = Path(temporary.name) / "test.db"
        override = patch.object(database, "DB_PATH", str(self.test_db_path))
        override.start()
        self.addCleanup(override.stop)
        database.init_db()
        database.seed_default_cases()
        with database.get_connection() as conn:
            conn.execute('INSERT INTO reviewer_accounts(id,username,salt,password_hash,role) VALUES (1,?,?,?,?)',
                ('test-reviewer', *_TEST_PASSWORD, 'ADMIN'))
        self.session_token = new_session(1)
        super().setUp()

    def fetch(self, path, **kwargs):
        headers = {'Cookie':f'riskora_session={self.session_token}', 'X-Riskora-Request':'1', 'Content-Type':'application/json'}
        headers.update(kwargs.pop('headers', {}))
        return super().fetch(path, headers=headers, **kwargs)

    def approve_seed(self, rate=18.5, term=36):
        from tests.test_foundation import COMPLETE_PROFILE
        profile = {**COMPLETE_PROFILE, 'name':'Test borrower', 'LoanAmount':120000,'InterestRate':rate,'LoanTerm':term}
        response = self.fetch('/api/loans/LR-1054/edit', method='POST', body=json.dumps(profile))
        self.assertEqual(response.code,200,response.body)
        response = self.fetch('/api/risk/analyze',method='POST',body=json.dumps({'loanId':'LR-1054'}))
        self.assertEqual(response.code,200,response.body)
        detail = json.loads(self.fetch('/api/loans/LR-1054').body)
        response = self.fetch('/api/loans/LR-1054/review',method='POST',body=json.dumps({'decision':'APPROVED','note':'Reviewed for test fixture.','assessment_id':detail['assessment']['id']}))
        self.assertEqual(response.code,200,response.body)

    def fund_seed(self, rate=12, term=12):
        self.approve_seed(rate,term)
        response = self.fetch('/api/funding/optimize',method='POST',body=json.dumps({'loanId':'LR-1054','amount':120000,'mode':'fractional'}))
        self.assertEqual(response.code,200,response.body)
        return json.loads(response.body)

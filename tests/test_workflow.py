import json
from tornado.testing import AsyncHTTPTestCase
from backend.server import make_app
from backend.services.funding_service import FundingService
from backend.services.repayment_service import RepaymentService
from tests.support import IsolatedDatabaseMixin

class WorkflowRegressionTests(IsolatedDatabaseMixin, AsyncHTTPTestCase):
    def get_app(self): return make_app()
    def post(self, path, body, status=200):
        response = self.fetch(path, method='POST', body=json.dumps(body))
        self.assertEqual(response.code, status, response.body.decode())
        return json.loads(response.body)
    def test_saved_contract_and_payment_guards(self):
        fund = self.post('/api/funding/optimize', dict(loanId='LR-1054', amount=120000, mode='fractional'))
        plan = self.post('/api/repayment/generate', dict(loanId='LR-1054', principal=120000, rate=0, term=12, positions=fund['positions']))
        def detail(): return json.loads(self.fetch('/api/loans/LR-1054').body)
        saved = detail()
        for key in ('total_requested', 'lender_count', 'largest_lender_share'):
            self.assertEqual(saved['funding'][key], fund[key])
        for key in ('original_principal', 'annual_interest_rate', 'num_installments', 'allocation_policy_description'):
            self.assertEqual(saved['repayment'][key], plan[key])
        self.assertEqual(len(saved['repayment']['lender_summary']), 3)
        self.assertFalse(any(i['status'] == 'PAID' for i in saved['repayment']['installments']))
        for amount in (0, -1, 1, 10001):
            self.post('/api/repayment/record', dict(loanId='LR-1054', installmentNum=1, amount=amount), 400)
        self.post('/api/repayment/record', dict(loanId='LR-1054', installmentNum=1, amount=10000))
        self.post('/api/repayment/record', dict(loanId='LR-1054', installmentNum=1, amount=10000), 409)
        saved = detail()['repayment']
        self.assertEqual(saved['num_installments'], 12)
        self.assertEqual(saved['installments'][0]['status'], 'PAID')
        self.post('/api/repayment/generate', dict(loanId='LR-1054'), 409)
        self.post('/api/funding/optimize', dict(loanId='LR-1054'), 409)
    def test_allocations_reconcile_to_cent_for_all_policies(self):
        funding = FundingService.calculate_structure(123457.13, 'HIGH', 'fractional', 5)
        for policy in ('pro-rata', 'largest-first', 'earliest-first'):
            plan = RepaymentService.generate_schedule(123457.13, 12.3, 37, allocation_policy=policy, lender_positions=funding['positions'])
            for inst in plan['installments']:
                for source, allocated in [('payment_amount','total_allocated'), ('principal_component','principal_allocated'), ('interest_component','interest_allocated')]:
                    self.assertEqual(round(inst[source]*100), sum(round(a[allocated]*100) for a in inst['allocations']))
            for pos in funding['positions']:
                paid = sum(round(a['principal_allocated']*100) for i in plan['installments'] for a in i['allocations'] if a['lender_id'] == pos['lender_id'])
                self.assertEqual(paid, round(pos['committed_amount']*100))

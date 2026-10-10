"""ORA review brief adapted from the incoming OraAgent project.

This is deterministic decision support using saved evidence, not an autonomous
agent, bureau rating, identity verification or permission to commit funding.
"""
import hashlib
import json


def build_brief(loan, assessment):
    quality = json.loads(assessment['dq_details_json'] or '{}')
    snapshot = json.loads(assessment.get('input_snapshot_json') or '{}')
    warnings = quality.get('validity_warnings', []) + quality.get('contradiction_flags', [])
    missing = quality.get('missing_required_fields', []) + quality.get('missing_optional_fields', [])
    return {
        'loan_id': loan['id'], 'assessment_id': assessment['id'],
        'source': 'Saved calibrated model assessment and input-quality policy rules',
        'model_version': assessment['model_version'],
        'probability_of_default': assessment['probability_of_default'],
        'risk_level': assessment['risk_level'],
        'display_score': assessment['risk_score'],
        'verdict': (f"Recorded loan stage: {loan['status'].replace('_',' ')}. See the reviewer decision below." if loan['status'] in ('APPROVED','REJECTED','FUNDED','REPAYMENT_CONFIGURED','REPAYING','CLOSED','FULLY_PAID') else 'Resolve missing inputs and warnings before review.' if not quality.get('verification_ready')
                    else 'Human review required before approval and funding.'),
        'evidence': [
            {'factor': 'Income', 'value': snapshot.get('Income'), 'source': 'Borrower input; documents not verified'},
            {'factor': 'Debt-to-income ratio', 'value': snapshot.get('DTIRatio'), 'source': 'Borrower input'},
            {'factor': 'Credit score', 'value': snapshot.get('CreditScore'), 'source': 'Borrower input; bureau connection not configured'},
        ],
        'warnings': warnings, 'missing_fields': missing,
        'policy_indicators': json.loads(assessment['drivers_json'] or '[]'),
        'input_digest': hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
        'disclosure': 'Synthetic-data model. The input digest identifies a snapshot; it is not external verification or a compliance certificate.',
    }

"""Integer-cent partial payments against immutable scheduled lender allocations."""
from decimal import Decimal, InvalidOperation


def cents(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number != number.quantize(Decimal('0.01')):
            raise ValueError('Amounts must have at most two decimal places.')
        return int(number * 100)
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid monetary amount.') from None


def apply_payment(target, amount):
    amount = cents(amount)
    due = cents(target['payment_amount']) - cents(target.get('actual_amount_paid', 0))
    if amount <= 0 or amount > due:
        raise ValueError('Payment must be positive and no greater than the remaining installment amount.')
    existing = {a['lender_id']:a for a in target.get('paid_allocations', [])}
    buckets = []
    for a in target['allocations']:
        old = existing.get(a['lender_id'], {})
        for field in ('principal_allocated', 'interest_allocated'):
            buckets.append((a, field, cents(a[field])-cents(old.get(field,0))))
    total = sum(b[2] for b in buckets)
    if total != due: raise ValueError('Schedule allocations do not reconcile. Review the schedule.')
    shares = [amount*b[2]//total for b in buckets]
    ranked = sorted(range(len(buckets)), key=lambda i: (amount*buckets[i][2])%total, reverse=True)
    for i in ranked[:amount-sum(shares)]: shares[i] += 1
    receipt = {}
    for (a,field,_), share in zip(buckets,shares):
        row = receipt.setdefault(a['lender_id'], {'lender_id':a['lender_id'], 'lender_name':a['lender_name'],
            'principal_allocated':0, 'interest_allocated':0})
        row[field] = share/100
    for row in receipt.values():
        row['total_allocated'] = (cents(row['principal_allocated'])+cents(row['interest_allocated']))/100
        old = existing.setdefault(row['lender_id'],dict(lender_id=row['lender_id'], lender_name=row['lender_name'],principal_allocated=0,interest_allocated=0,total_allocated=0))
        for field in ('principal_allocated','interest_allocated','total_allocated'):
            old[field] = (cents(old[field])+cents(row[field]))/100
    target['paid_allocations'] = list(existing.values())
    target['actual_amount_paid'] = (cents(target.get('actual_amount_paid',0))+amount)/100
    target['principal_paid'] = sum(cents(a['principal_allocated']) for a in existing.values())/100
    target['status'] = 'PAID' if amount == due else 'PARTIAL'
    return list(receipt.values())

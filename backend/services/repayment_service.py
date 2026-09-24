"""
RISKORA — Amortisation & Repayment Waterfall Allocation Service
Generates exact schedules for multiple repayment frequencies (Monthly, Bi-Monthly, Custom, Flexible)
and applies institutional waterfall repayment allocation policies (Pro-Rata, LCF, FIFO).
"""

import datetime
from typing import Dict, Any, List

class RepaymentService:
    @classmethod
    def generate_schedule(
        cls,
        principal: float,
        annual_rate_pct: float,
        term_months: int,
        start_date_str: str = None,
        schedule_type: str = "monthly",  # 'monthly', 'bi-monthly', 'custom', 'flexible'
        allocation_policy: str = "pro-rata",  # 'pro-rata', 'largest-first', 'earliest-first'
        lender_positions: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generates full amortisation schedule with separate principal/interest tracking
        and exact zero-balance final penny reconciliation.
        """
        principal = float(principal)
        annual_rate = float(annual_rate_pct) / 100.0
        term_months = max(1, int(term_months))
        
        if not start_date_str:
            base_date = datetime.date.today() + datetime.timedelta(days=30)
        else:
            try:
                base_date = datetime.date.fromisoformat(start_date_str)
            except ValueError:
                base_date = datetime.date.today() + datetime.timedelta(days=30)

        # Determine frequency parameters
        if schedule_type == "bi-monthly":
            # 2 payments per month
            num_installments = term_months * 2
            periodic_rate = annual_rate / 24.0
            days_step = 15
        else:
            # monthly, custom, or flexible
            num_installments = term_months
            periodic_rate = annual_rate / 12.0
            days_step = 30

        # Calculate EMI via annuity formula
        if periodic_rate > 0:
            emi = principal * periodic_rate * ((1.0 + periodic_rate) ** num_installments) / (((1.0 + periodic_rate) ** num_installments) - 1.0)
        else:
            emi = principal / num_installments
            
        emi = round(emi, 2)
        
        # Prepare lender tracking structures
        if not lender_positions:
            lender_positions = [{
                "lender_id": "LND-001",
                "lender_name": "Apex Micro-Credit Fund",
                "share_pct": 100.0,
                "committed_amount": principal
            }]
            
        lender_balances = {
            pos["lender_id"]: {
                "name": pos["lender_name"],
                "share_pct": pos["share_pct"],
                "initial_principal": pos["committed_amount"],
                "outstanding_principal": pos["committed_amount"],
                "total_principal_received": 0.0,
                "total_interest_received": 0.0
            }
            for pos in lender_positions
        }

        installments = []
        balance = principal
        total_interest_accrued = 0.0
        
        for i in range(1, num_installments + 1):
            if schedule_type == "bi-monthly":
                month_offset = (i - 1) // 2
                day = 5 if (i % 2 == 1) else 20
                year = base_date.year + (base_date.month - 1 + month_offset) // 12
                month = (base_date.month - 1 + month_offset) % 12 + 1
                due_date = datetime.date(year, month, min(day, 28))
            elif schedule_type == "flexible":
                # Flexible window: e.g. 1st to 7th
                year = base_date.year + (base_date.month - 1 + i - 1) // 12
                month = (base_date.month - 1 + i - 1) % 12 + 1
                due_date = datetime.date(year, month, min(base_date.day, 28))
            else:
                year = base_date.year + (base_date.month - 1 + i - 1) // 12
                month = (base_date.month - 1 + i - 1) % 12 + 1
                due_date = datetime.date(year, month, min(base_date.day, 28))

            interest_component = round(balance * periodic_rate, 2)
            total_interest_accrued += interest_component
            
            # Final installment balance absorption
            if i == num_installments:
                principal_component = round(balance, 2)
                installment_payment = round(principal_component + interest_component, 2)
                balance = 0.0
            else:
                principal_component = round(min(balance, emi - interest_component), 2)
                installment_payment = round(principal_component + interest_component, 2)
                balance = round(balance - principal_component, 2)

            # Compute lender allocation for this installment
            allocations = cls._allocate_installment(
                installment_payment,
                principal_component,
                interest_component,
                allocation_policy,
                lender_balances
            )

            installments.append({
                "installment_num": i,
                "due_date": due_date.isoformat(),
                "payment_window": f"{due_date.isoformat()} to {(due_date + datetime.timedelta(days=6)).isoformat()}" if schedule_type == "flexible" else None,
                "payment_amount": installment_payment,
                "principal_component": principal_component,
                "interest_component": interest_component,
                "remaining_balance": max(0.0, balance),
                "status": "SCHEDULED",
                "allocations": allocations
            })

        total_repayable = round(principal + total_interest_accrued, 2)

        return {
            "schedule_type": schedule_type,
            "allocation_policy": allocation_policy,
            "original_principal": principal,
            "annual_interest_rate": annual_rate_pct,
            "term_months": term_months,
            "num_installments": num_installments,
            "indicative_emi": emi,
            "total_interest": round(total_interest_accrued, 2),
            "total_repayable": total_repayable,
            "installments": installments,
            "lender_summary": [
                {
                    "lender_id": lid,
                    "lender_name": info["name"],
                    "committed_capital": info["initial_principal"],
                    "expected_principal": info["initial_principal"],
                    "expected_interest": round(info["total_interest_received"], 2),
                    "total_expected_return": round(info["initial_principal"] + info["total_interest_received"], 2)
                }
                for lid, info in lender_balances.items()
            ],
            "allocation_policy_description": cls._get_policy_description(allocation_policy)
        }

    @classmethod
    def _allocate_installment(
        cls,
        payment: float,
        principal_comp: float,
        interest_comp: float,
        policy: str,
        lender_balances: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Splits installment into principal and interest across lenders
        according to the selected institutional allocation policy.
        """
        allocations = []
        lender_ids = list(lender_balances.keys())
        
        # Interest is always distributed pro-rata based on committed capital share
        for lid in lender_ids:
            info = lender_balances[lid]
            share_ratio = info["share_pct"] / 100.0
            interest_share = round(interest_comp * share_ratio, 2)
            info["total_interest_received"] += interest_share

        if policy == "largest-first":
            # Priority principal to largest outstanding exposure
            rem_principal = principal_comp
            # Sort lenders by current outstanding principal descending
            sorted_lenders = sorted(lender_ids, key=lambda lid: lender_balances[lid]["outstanding_principal"], reverse=True)
            
            prin_shares = {lid: 0.0 for lid in lender_ids}
            for lid in sorted_lenders:
                if rem_principal <= 0:
                    break
                avail = lender_balances[lid]["outstanding_principal"]
                take = min(avail, rem_principal)
                prin_shares[lid] = round(take, 2)
                rem_principal = round(rem_principal - take, 2)
                
            for lid in lender_ids:
                info = lender_balances[lid]
                p_share = prin_shares[lid]
                info["outstanding_principal"] = max(0.0, round(info["outstanding_principal"] - p_share, 2))
                info["total_principal_received"] += p_share
                
                share_ratio = info["share_pct"] / 100.0
                i_share = round(interest_comp * share_ratio, 2)
                
                allocations.append({
                    "lender_id": lid,
                    "lender_name": info["name"],
                    "principal_allocated": p_share,
                    "interest_allocated": i_share,
                    "total_allocated": round(p_share + i_share, 2)
                })

        elif policy == "earliest-first":
            # FIFO: Earlier-funded positions receive priority principal
            rem_principal = principal_comp
            prin_shares = {lid: 0.0 for lid in lender_ids}
            for lid in lender_ids:  # natural insertion order represents funding timestamp
                if rem_principal <= 0:
                    break
                avail = lender_balances[lid]["outstanding_principal"]
                take = min(avail, rem_principal)
                prin_shares[lid] = round(take, 2)
                rem_principal = round(rem_principal - take, 2)
                
            for lid in lender_ids:
                info = lender_balances[lid]
                p_share = prin_shares[lid]
                info["outstanding_principal"] = max(0.0, round(info["outstanding_principal"] - p_share, 2))
                info["total_principal_received"] += p_share
                
                share_ratio = info["share_pct"] / 100.0
                i_share = round(interest_comp * share_ratio, 2)
                
                allocations.append({
                    "lender_id": lid,
                    "lender_name": info["name"],
                    "principal_allocated": p_share,
                    "interest_allocated": i_share,
                    "total_allocated": round(p_share + i_share, 2)
                })
        else:
            # Default: Pro-Rata Allocation
            for lid in lender_ids:
                info = lender_balances[lid]
                share_ratio = info["share_pct"] / 100.0
                p_share = round(principal_comp * share_ratio, 2)
                i_share = round(interest_comp * share_ratio, 2)
                
                info["outstanding_principal"] = max(0.0, round(info["outstanding_principal"] - p_share, 2))
                info["total_principal_received"] += p_share
                
                allocations.append({
                    "lender_id": lid,
                    "lender_name": info["name"],
                    "principal_allocated": p_share,
                    "interest_allocated": i_share,
                    "total_allocated": round(p_share + i_share, 2)
                })

        return allocations

    @classmethod
    def _get_policy_description(cls, policy: str) -> str:
        if policy == "largest-first":
            return "Largest Contribution First (Waterfall): Priority principal reimbursement is directed to the participant with the largest outstanding exposure until balances equalize."
        elif policy == "earliest-first":
            return "Earliest Funding First (FIFO Waterfall): Lenders who committed capital earliest receive priority principal reimbursement before later tranches."
        return "Pro-Rata Allocation (Default): Every installment is apportioned strictly proportional to original committed capital percentages."

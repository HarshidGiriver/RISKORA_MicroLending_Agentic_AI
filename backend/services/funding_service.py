"""
RISKORA — Institutional Funding Structure Engine
Calculates single-lender vs. fractional loan syndication structures,
lender allocation shares, and Herfindahl-Hirschman Index (HHI) concentration metrics.
"""

from typing import Dict, Any, List

class FundingService:
    DEFAULT_LENDER_NAMES = [
        "Apex Micro-Credit Fund",
        "Beacon Capital Partners",
        "Crestline Lending Syndicate",
        "Delta Prime Liquidity",
        "Equinox Debt Strategies",
        "Frontier Institutional Trust"
    ]

    @classmethod
    def calculate_structure(
        cls, 
        loan_amount: float, 
        risk_level: str, 
        mode: str = "auto", 
        lender_count: int = 3,
        custom_weights: List[float] = None
    ) -> Dict[str, Any]:
        """
        Calculates syndicated participation, exact rupee capital commitments,
        and lender exposure concentration (HHI).
        """
        # Determine recommended mode
        if mode == "auto":
            if risk_level == "HIGH":
                selected_mode = "fractional"
                rationale = "High borrower default hazard requires fractional syndication to avoid concentrated capital impairment on a single lender."
            elif risk_level == "MEDIUM" and loan_amount >= 60000:
                selected_mode = "fractional"
                rationale = "Elevated exposure size under moderate risk warrants multi-lender risk sharing."
            else:
                selected_mode = "single"
                rationale = "Borrower risk profile and exposure size are suitable for single-lender funding."
        else:
            selected_mode = mode
            rationale = "Structure manually selected by risk underwriter."

        lender_count = max(2, min(6, int(lender_count)))
        
        positions = []
        if selected_mode == "single":
            positions.append({
                "lender_id": "LND-001",
                "lender_name": cls.DEFAULT_LENDER_NAMES[0],
                "share_pct": 100.0,
                "committed_amount": round(loan_amount, 2),
                "is_lead": True
            })
            hhi = 10000.0
            largest_share = 100.0
            concentration_rating = "HIGH_CONCENTRATION"
            concentration_desc = "100% of loan exposure is carried by a single institutional lender."
        else:
            # Fractional syndication: default descending weights (lead takes larger share)
            if not custom_weights or len(custom_weights) != lender_count:
                raw_weights = [lender_count - i * 0.7 for i in range(lender_count)]
            else:
                raw_weights = custom_weights
                
            total_w = sum(raw_weights)
            shares = [round((w / total_w) * 100, 2) for w in raw_weights]
            # Ensure shares sum exactly to 100.0%
            diff = round(100.0 - sum(shares), 2)
            shares[0] = round(shares[0] + diff, 2)
            
            allocated_amounts = [round(loan_amount * (s / 100.0), 2) for s in shares]
            amt_diff = round(loan_amount - sum(allocated_amounts), 2)
            allocated_amounts[0] = round(allocated_amounts[0] + amt_diff, 2)
            
            for idx in range(lender_count):
                positions.append({
                    "lender_id": f"LND-{101 + idx}",
                    "lender_name": cls.DEFAULT_LENDER_NAMES[idx % len(cls.DEFAULT_LENDER_NAMES)],
                    "share_pct": shares[idx],
                    "committed_amount": allocated_amounts[idx],
                    "is_lead": idx == 0
                })
                
            # Herfindahl-Hirschman Index (HHI) = Sum(s_i ^ 2)
            hhi = round(sum(s ** 2 for s in shares), 1)
            largest_share = max(shares)
            
            if hhi > 5000:
                concentration_rating = "HIGH_CONCENTRATION"
                concentration_desc = f"Largest lender carries {largest_share}%. Material single-counterparty exposure remains."
            elif hhi >= 2500:
                concentration_rating = "MODERATE_CONCENTRATION"
                concentration_desc = f"Exposure distributed across {lender_count} lenders. Lead lender holds {largest_share}%."
            else:
                concentration_rating = "WELL_DISTRIBUTED"
                concentration_desc = f"Diversified syndication across {lender_count} lenders with minimal concentration (HHI: {hhi})."

        return {
            "mode": selected_mode,
            "total_requested": loan_amount,
            "funded_amount": loan_amount,
            "remaining_amount": 0.0,
            "lender_count": len(positions),
            "positions": positions,
            "herfindahl_index": hhi,
            "largest_lender_share": largest_share,
            "concentration_rating": concentration_rating,
            "concentration_description": concentration_desc,
            "decision_rationale": rationale,
            "critical_risk_distinction": (
                "IMPORTANT CONCEPTUAL DISTINCTION: Fractional funding distributes lender exposure concentration "
                "across multiple participants. It does NOT reduce the borrower's fundamental probability of default."
            )
        }
